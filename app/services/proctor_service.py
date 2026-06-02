"""
EduProctorAI - Proctor Service for face and eye tracking
"""
import base64
import numpy as np
import cv2
import mediapipe as mp
from typing import Dict, Any, Tuple
import logging

logger = logging.getLogger(__name__)


class ProctorService:
    def __init__(self):
        self.face_mesh = None
        self.movement_threshold = 0.03
        self.last_landmarks = None
        self._init_face_mesh()

    def _init_face_mesh(self):
        try:
            self.face_mesh = mp.solutions.face_mesh.FaceMesh(
                static_image_mode=False,
                max_num_faces=1,
                refine_landmarks=True,
                min_detection_confidence=0.5,
                min_tracking_confidence=0.5
            )
            logger.info("FaceMesh initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize FaceMesh: {str(e)}")
            self.face_mesh = None

    def analyze_frame(self, frame_base64: str) -> Dict[str, Any]:
        if not self.face_mesh:
            return {
                "face_detected": False,
                "movement_detected": False,
                "movement_amount": 0,
                "eye_movement": {"looking_away": False, "direction": "center"},
                "warning": "FaceMesh not initialized"
            }

        try:
            if ',' in frame_base64:
                frame_base64 = frame_base64.split(',')[1]
            img_data = base64.b64decode(frame_base64)
            nparr = np.frombuffer(img_data, np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

            if frame is None:
                return {"face_detected": False, "movement_detected": False}

            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = self.face_mesh.process(rgb_frame)

            if not results.multi_face_landmarks:
                return {"face_detected": False, "movement_detected": False}

            landmarks = results.multi_face_landmarks[0]
            current_points = self._extract_key_points(landmarks)

            movement_detected, movement_amount = self._detect_movement(current_points)
            eye_movement = self._detect_eye_movement(landmarks)

            self.last_landmarks = current_points

            return {
                "face_detected": True,
                "movement_detected": movement_detected,
                "movement_amount": movement_amount,
                "eye_movement": eye_movement,
                "face_position": {
                    "center_x": current_points.get("nose_tip", [0, 0, 0])[0],
                    "center_y": current_points.get("nose_tip", [0, 0, 0])[1],
                    "width": 0.3,
                    "height": 0.3
                }
            }

        except Exception as e:
            logger.error(f"Frame analysis error: {str(e)}")
            return {"face_detected": False, "movement_detected": False}

    def _extract_key_points(self, landmarks) -> Dict[str, list]:
        points = {
            "nose_tip": [landmarks.landmark[1].x, landmarks.landmark[1].y, landmarks.landmark[1].z],
            "left_eye": [landmarks.landmark[33].x, landmarks.landmark[33].y, landmarks.landmark[33].z],
            "right_eye": [landmarks.landmark[263].x, landmarks.landmark[263].y, landmarks.landmark[263].z],
            "left_eye_inner": [landmarks.landmark[133].x, landmarks.landmark[133].y, landmarks.landmark[133].z],
            "right_eye_inner": [landmarks.landmark[362].x, landmarks.landmark[362].y, landmarks.landmark[362].z],
        }
        return points

    def _detect_movement(self, current_points: Dict) -> Tuple[bool, float]:
        if not self.last_landmarks:
            return False, 0.0

        total_movement = 0
        key_points = ["nose_tip", "left_eye", "right_eye"]

        for point in key_points:
            if point in current_points and point in self.last_landmarks:
                dist = np.sqrt(
                    (current_points[point][0] - self.last_landmarks[point][0]) ** 2 +
                    (current_points[point][1] - self.last_landmarks[point][1]) ** 2 +
                    (current_points[point][2] - self.last_landmarks[point][2]) ** 2
                )
                total_movement += dist

        avg_movement = total_movement / len(key_points)
        return avg_movement > self.movement_threshold, round(avg_movement, 4)

    def _detect_eye_movement(self, landmarks) -> Dict[str, Any]:
        try:
            left_iris = landmarks.landmark[468] if len(landmarks.landmark) > 468 else None
            right_iris = landmarks.landmark[473] if len(landmarks.landmark) > 473 else None

            if not left_iris or not right_iris:
                return {"looking_away": False, "direction": "center", "gaze_x": 0.5}

            left_outer = landmarks.landmark[33]
            left_inner = landmarks.landmark[133]
            right_outer = landmarks.landmark[362]
            right_inner = landmarks.landmark[263]

            left_width = abs(left_inner.x - left_outer.x)
            right_width = abs(right_inner.x - right_outer.x)

            if left_width > 0 and right_width > 0:
                left_gaze = (left_iris.x - left_outer.x) / left_width
                right_gaze = (right_iris.x - right_outer.x) / right_width
                avg_gaze = (left_gaze + right_gaze) / 2

                if avg_gaze < 0.3:
                    return {"looking_away": True, "direction": "left", "gaze_x": round(avg_gaze, 3)}
                elif avg_gaze > 0.7:
                    return {"looking_away": True, "direction": "right", "gaze_x": round(avg_gaze, 3)}
                else:
                    return {"looking_away": False, "direction": "center", "gaze_x": round(avg_gaze, 3)}

        except Exception as e:
            logger.warning(f"Eye movement detection error: {str(e)}")

        return {"looking_away": False, "direction": "center", "gaze_x": 0.5}