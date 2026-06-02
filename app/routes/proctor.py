"""
EduProctorAI - Proctoring Routes
"""
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
from datetime import datetime
import json
import logging
from typing import Dict

from .. import models, auth, database
from ..config import settings
from ..services.proctor_service import ProctorService

router = APIRouter()
logger = logging.getLogger(__name__)

active_connections: Dict[int, WebSocket] = {}
proctor_service = ProctorService()


@router.websocket("/ws/{test_result_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    test_result_id: int
):
    await websocket.accept()
    logger.info(f"WebSocket connected for test_result {test_result_id}")

    try:
        auth_data = await websocket.receive_json()
        if auth_data.get('type') != 'auth' or not auth_data.get('token'):
            logger.warning(f"WebSocket auth failed: no token")
            await websocket.close(code=1008)
            return

        payload = auth.decode_token(auth_data.get('token'))
        if not payload:
            logger.warning(f"WebSocket auth failed: invalid token")
            await websocket.close(code=1008)
            return

        student_id = payload.get("user_id")
        db = next(database.get_db())

        try:
            test_result = db.query(models.TestResult).filter(
                models.TestResult.id == test_result_id
            ).first()

            if not test_result or test_result.student_id != student_id:
                logger.warning(f"WebSocket auth failed: invalid test_result")
                await websocket.close(code=1008)
                return

            active_connections[test_result_id] = websocket

            session_data = {
                "movements": [],
                "eye_movements": [],
                "timestamps": [],
                "movement_count": 0,
                "start_time": datetime.utcnow().isoformat()
            }

            await websocket.send_json({
                "type": "ready",
                "message": "Proctoring active",
                "session_id": test_result_id,
                "start_time": session_data["start_time"]
            })

            while True:
                data = await websocket.receive_json()

                if data['type'] == 'frame':
                    frame_data = data.get('frame', '')
                    analysis = proctor_service.analyze_frame(frame_data)

                    session_data["timestamps"].append(datetime.utcnow().isoformat())
                    if analysis.get('movement_detected'):
                        session_data["movement_count"] += 1
                        session_data["movements"].append({
                            "timestamp": datetime.utcnow().isoformat(),
                            "amount": analysis.get('movement_amount', 0)
                        })

                    if analysis.get('eye_movement', {}).get('looking_away'):
                        session_data["eye_movements"].append({
                            "timestamp": datetime.utcnow().isoformat(),
                            "direction": analysis.get('eye_movement', {}).get('direction', 'unknown')
                        })

                    await websocket.send_json({
                        "type": "analysis",
                        "face_detected": analysis.get('face_detected', False),
                        "movement_detected": analysis.get('movement_detected', False),
                        "movement_amount": analysis.get('movement_amount', 0),
                        "eye_movement": analysis.get('eye_movement', {}),
                        "movement_count": session_data["movement_count"],
                        "timestamp": datetime.utcnow().isoformat()
                    })

                elif data['type'] == 'ping':
                    await websocket.send_json({"type": "pong"})

                elif data['type'] == 'close':
                    logger.info(f"WebSocket closing for test_result {test_result_id}")
                    break

        finally:
            db.close()

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for test_result {test_result_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {str(e)}")
    finally:
        if test_result_id in active_connections:
            del active_connections[test_result_id]


@router.post("/submit")
async def submit_proctor_data(
    data: dict,
    db: Session = Depends(database.get_db),
    token: str = Depends(auth.oauth2_scheme)
):
    payload = auth.decode_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Not authenticated")

    student_id = payload.get("user_id")
    test_id = data.get("testId")
    answers = data.get("answers", {})
    proctor_data = data.get("proctorData", {})
    movement_count = proctor_data.get("movementCount", 0)

    test = db.query(models.Test).filter(models.Test.id == test_id).first()
    if not test:
        raise HTTPException(status_code=404, detail="Test not found")

    from ..utils.helpers import calculate_test_score
    score_result = calculate_test_score(test, answers)

    penalty = min(movement_count * 1.0, 30.0)
    final_score = max(0, score_result["score"] - penalty)

    test_result = models.TestResult(
        student_id=student_id,
        test_id=test_id,
        score=final_score,
        max_score=score_result["max_score"],
        percentage=(final_score / score_result["max_score"]) * 100 if score_result["max_score"] > 0 else 0,
        answers=answers,
        proctor_notes=proctor_data,
        movement_count=movement_count,
        penalty_points=penalty,
        started_at=datetime.fromisoformat(data.get("startedAt")) if data.get("startedAt") else datetime.utcnow(),
        completed_at=datetime.utcnow()
    )
    db.add(test_result)
    db.commit()
    db.refresh(test_result)

    proctor_session = models.ProctorSession(
        student_id=student_id,
        test_result_id=test_result.id,
        session_data=proctor_data.get("movementHistory", {}),
        eye_movements=proctor_data.get("eyeMovements", []),
        face_movements=proctor_data.get("faceMovements", []),
        window_switches=proctor_data.get("windowSwitches", []),
        timestamps=proctor_data.get("timestamps", [])
    )
    db.add(proctor_session)
    db.commit()

    return {
        "success": True,
        "result_id": test_result.id,
        "score": final_score,
        "percentage": test_result.percentage
    }