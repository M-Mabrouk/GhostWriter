# import the necessary packages
import numpy as np
import cv2
from src.Globals import constants, utility
import imutils
from src import gcv_ocr, calibration
import time
import os

timestr = time.strftime("%Y%m%d_%H%M%S")
pdf_folder = '../document/image/pdf{}'.format(timestr)
os.mkdir(pdf_folder)

pipeline, profile = utility.createPipline()
filters = utility.createFilters()
points = None
pts = None
drawn = []
time.sleep(2.0)

config = calibration.Calibrator(pipeline, profile, filters)
paper = np.zeros((config.PAPER_HEIGHT, config.PAPER_WIDTH, 3), np.uint8) + 255
print(paper.shape)

# keep looping
while True:
    key = cv2.waitKey(1) & 0xFF
    if key == ord("q"):
        pipeline.stop()
        break
    elif key == ord("c"):
        paper = np.zeros((config.PAPER_HEIGHT, config.PAPER_WIDTH, 3), np.uint8) + 255
        drawn = []
        points = None

    elif key == ord("s"):
        utility.saveJPG(pdf_folder, paper)
        utility.savePGF("pdf_{}".format(timestr), pdf_folder, '../document/pdf')
        text = gcv_ocr.detect_text(pdf_folder)
        gcv_ocr.write_ON_File(text, timestr)

    elif key == ord("n"):
        utility.saveJPG(pdf_folder, paper)
        paper = np.zeros((config.PAPER_HEIGHT, config.PAPER_WIDTH, 3), np.uint8) + 255
        drawn = []
        points = None

    frame, depth = utility.Fetch(pipeline)
    intrinsics = depth.profile.as_video_stream_profile().intrinsics
    depth = utility.PostProcessing(filters, depth)

    colorized_depth = utility.ColorizeDepth(depth)
    depth = np.asanyarray(depth.get_data())
    # _, frame = utility.align(frame, colorized_depth)

    frameResized = imutils.resize(frame, width=constants.RESIZED_WIDTH)
    # TODO: use object detection instead of color detection

    cnts = utility.Contours(frameResized)
    center = None

    if len(cnts) > 0:
        c = max(cnts, key=cv2.contourArea)
        extBot = tuple(c[c[:, :, 1].argmax()][0])
        ((x, y), radius) = cv2.minEnclosingCircle(c)
        M = cv2.moments(c)
        center = (int(M["m10"] / M["m00"]), int(M["m01"] / M["m00"]))

        if radius >= constants.ALLOWED_RADIUS:
            # TODO: add screen to world x,y transformer
            (cXr, cYr), (cX, cY) = utility.getCenter(center, (x, y))
            cXp, cYp, _ = utility.transformer(cX, cY, intrinsics, config.DEPTH_SCALE)
            # cX, cY = extBot
            # cX = int(round(cX * (constants.WIDTH / constants.RESIZED_WIDTH)))
            # cY = int(round(cY * (constants.HEIGHT / constants.RESIZED_HEIGHT))) - 15
            # TODO: sync color and depth frame to avoid wrong depth calculation
            Z = int(depth[cY, cX] * config.DEPTH_SCALE)
            dZ = min(max(0, int(Z - config.Near)), config.Far)
            if cY < config.HEIGHT_THRESHOLD or not (config.Near < Z < config.Far) or not (
                    config.Right < cX < config.Left):
                if points is not None:
                    drawn.append(points)
                points = None


            else:
                distanceFactor = ((1 - dZ / paper.shape[1]) + (dZ / config.PAPER_HEIGHT) * config.PrespectiveEffect)
                dX = round(
                    (min(max(0, int(cX - config.Right)), config.Left)))  # - config.PAPER_WIDTH / 2) * distanceFactor
                # + config.PAPER_WIDTH / 2)
                if points is None:
                    points = [[dX, dZ]]
                else:
                    points.append([dX, dZ])
                    pts = np.asanyarray(points, np.int32).reshape((-1, 1, 2))
                    cv2.polylines(paper, [pts], False, (0, 0, 0), lineType=cv2.LINE_AA)

            # TODO: remove after debugging
            ###################################################################
            text = "X: " + str(cX) + ",Y: " + str(cY) + ",Z: " + str(Z)
            cv2.circle(frameResized, (int(x), int(y)), int(radius), (0, 255, 255), 2)
            cv2.putText(frameResized, text, (0, 15), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (125, 125, 125), 2)
            cv2.circle(frameResized, (cXr, cYr), 2, (0, 0, 255), -1)
            cv2.circle(colorized_depth, (cX, cY), 2, (0, 255, 0), -1)
            ###################################################################
    viewport = paper.copy()
    viewport = cv2.flip(viewport, 1)
    # viewport = cv2.blur(viewport, (5, 5), 0)
    # kernel = np.ones((5, 5), np.float32) / 25
    # viewport = cv2.filter2D(viewport, -1, kernel)
    cv2.namedWindow('Frame', cv2.WINDOW_AUTOSIZE)
    cv2.namedWindow('Depth', cv2.WINDOW_AUTOSIZE)
    cv2.namedWindow('Paper', cv2.WINDOW_NORMAL)
    cv2.resizeWindow('Paper', 480, 640)

    cv2.imshow("Frame", frameResized)
    cv2.imshow("Depth", colorized_depth)
    cv2.imshow("Paper", viewport)

with open('SavedPoints\points_{}.txt'.format(timestr), 'w') as f:
    for item in drawn:
        f.write("%s\n".replace("[","").replace("]","") % item)

# close all windows
cv2.destroyAllWindows()