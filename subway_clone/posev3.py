import cv2
import mediapipe as mp
import time
import numpy as np
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

# Global storage for tracking the latest async frame detection data
latest_result = None

def tracking_callback(result: vision.PoseLandmarkerResult, output_image: mp.Image, timestamp_ms: int):
    """Callback function executed whenever the model finishes processing a live frame."""
    global latest_result
    latest_result = result

def main():
    global latest_result
    
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("ERROR: Could not access the webcam.")
        return

    # STEP 1: Set up options for the new Tasks API Engine
    model_path = "pose_landmarker.task"
    base_options = python.BaseOptions(model_asset_path=model_path)
    
    options = vision.PoseLandmarkerOptions(
        base_options=base_options,
        running_mode=vision.RunningMode.LIVE_STREAM,
        min_pose_detection_confidence=0.6,
        min_tracking_confidence=0.6,
        result_callback=tracking_callback
    )

    # Tracking metrics for calibration thresholds
    min_shoulder_y = 1.0  # Peak Jump height tracking metric
    max_shoulder_y = 0.0  # Peak Duck height tracking metric

    print("\n=== SYSTEM RUNNING ===")
    print("Stand straight in the center grid alignment.")
    print("Press 'q' inside the video canvas screen to finish.\n")

    # STEP 2: Initialize the context manager
    with vision.PoseLandmarker.create_from_options(options) as detector:
        while cap.isOpened():
            ok, frame = cap.read()
            if not ok: break

            frame = cv2.flip(frame, 1)
            h, w, _ = frame.shape

            # Draw middle separation segment line
            cv2.line(frame, (w // 2, 0), (w // 2, h), (100, 100, 100), 1)

            # Convert standard OpenCV frame to MediaPipe Image format
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)

            # Generate precise monotonic timestamp markers (in milliseconds)
            frame_timestamp = int(time.time() * 1000)
            
            # Send asynchronous frame calculation to the tracker
            detector.detect_async(mp_image, frame_timestamp)

            # Process coordinates if the callback has updated data
            if latest_result and latest_result.pose_landmarks:
                # Target the primary landmark tracks (11: Left Shoulder, 12: Right Shoulder)
                landmarks = latest_result.pose_landmarks[0]
                
                left_s = landmarks[11]
                right_s = landmarks[12]

                mid_shoulder_x = (left_s.x + right_s.x) / 2
                mid_shoulder_y = (left_s.y + right_s.y) / 2

                # Record peak movement limits
                if mid_shoulder_y < min_shoulder_y: min_shoulder_y = mid_shoulder_y
                if mid_shoulder_y > max_shoulder_y: max_shoulder_y = mid_shoulder_y

                # Draw raw visual feedback point tracking circles
                cx, cy = int(mid_shoulder_x * w), int(mid_shoulder_y * h)
                cv2.circle(frame, (cx, cy), 8, (0, 255, 0), -1)

                # Render dynamic text parameters on the UI layout
                cv2.putText(frame, f"Current Norm X: {mid_shoulder_x:.3f}", (10, 60), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
                cv2.putText(frame, f"Peak Jump Y (Min): {min_shoulder_y:.3f}", (10, 90), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                cv2.putText(frame, f"Peak Duck Y (Max): {max_shoulder_y:.3f}", (10, 120), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)

            cv2.putText(frame, "Press 'q' to exit", (10, 30), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
            cv2.imshow("MediaPipe Tasks Calibration", frame)

            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

    cap.release()
    cv2.destroyAllWindows()

    print("\n=== CALIBRATION VALUES SECURED ===")
    print(f"Jump Boundary Min Y: {min_shoulder_y:.3f}")
    print(f"Duck Boundary Max Y: {max_shoulder_y:.3f}")

if __name__ == "__main__":
    main()