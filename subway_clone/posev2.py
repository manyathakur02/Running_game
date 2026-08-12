import cv2
from cvzone.PoseModule import PoseDetector

def main():
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("ERROR: could not open webcam.")
        return

    # Initialize the pose detector
    detector = PoseDetector(detectionCon=0.6, trackCon=0.6)

    # Tracking variables to catch your exact peak numbers
    min_shoulder_y = 1000.0  # Pixel coordinate max-height (Jump)
    max_shoulder_y = 0.0     # Pixel coordinate min-height (Duck)
    
    print("\n=== CALIBRATION STEP ===")
    print("1. Stand straight in the center of the frame.")
    print("2. Track your vertical shifts using pixel values.\n")

    while cap.isOpened():
        ok, frame = cap.read()
        if not ok: break

        frame = cv2.flip(frame, 1)
        h, w, _ = frame.shape
        
        # Find the pose and draw landmarks
        frame = detector.findPose(frame, draw=True)
        lmList, bboxInfo = detector.findPosition(frame, draw=False)

        # Draw center tracking line
        cv2.line(frame, (w // 2, 0), (w // 2, h), (100, 100, 100), 1)

        if lmList:
            # Landmark 11 is Left Shoulder, 12 is Right Shoulder
            # lmList[i] gives [x, y, z] in raw pixel values! Much easier to track.
            mid_shoulder_x = (lmList[11][0] + lmList[12][0]) / 2
            mid_shoulder_y = (lmList[11][1] + lmList[12][1]) / 2
            
            # Convert X to a normalized scale (0.0 to 1.0) for easy lane mapping
            norm_x = mid_shoulder_x / w

            # Update records if you are moving actively
            if mid_shoulder_y < min_shoulder_y: min_shoulder_y = mid_shoulder_y
            if mid_shoulder_y > max_shoulder_y: max_shoulder_y = mid_shoulder_y

            # On-screen debug text
            cv2.putText(frame, f"Current Norm X: {norm_x:.3f}", (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
            cv2.putText(frame, f"Peak Jump Y (Min Px): {int(min_shoulder_y)}", (10, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
            cv2.putText(frame, f"Peak Duck Y (Max Px): {int(max_shoulder_y)}", (10, 120), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)

            cx, cy = int(mid_shoulder_x), int(mid_shoulder_y)
            cv2.circle(frame, (cx, cy), 8, (0, 255, 0), -1)

        cv2.putText(frame, "Press 'q' to finish calibration", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        cv2.imshow("Pose Exploration & Calibration", frame)

        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()
    
    print("\n=== FINAL OBSERVED BOUNDARIES ===")
    print(f"Highest point reached (Jump Pixel Y): {int(min_shoulder_y)}")
    print(f"Lowest point reached (Duck Pixel Y): {int(max_shoulder_y)}")

if __name__ == "__main__":
    main()