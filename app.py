from flask import Flask, render_template, request, redirect, url_for, make_response, Response
import time
import cv2
import RPi.GPIO as GPIO
import common as cm
import numpy as np
from PIL import Image
from threading import Thread
import sys

cap = cv2.VideoCapture(0)

object_to_track = 'person'
threshold = 0.2
top_k = 1  # number of objects to be shown as detected


model_dir = '/home/pi/Desktop/Project'
model = 'mobilenet_ssd_v2_coco_quant_postprocess.tflite'
lbl = 'coco_labels.txt'

GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)
GPIO.cleanup()

dis = 0
GPIO_TRIGGER = 25
GPIO_ECHO = 24

# set GPIO direction (IN / OUT)
GPIO.setup(GPIO_TRIGGER, GPIO.OUT)
GPIO.setup(GPIO_ECHO, GPIO.IN)

in1 = 17  # stepper motor
in2 = 18
in3 = 27
in4 = 22

M1_1 = 11
M1_2 = 8
M2_1 = 9
M2_2 = 10
en1 = 21
en2 = 20

step_sleep = 0.001
step_count = 1024  # 5.625*(1/64) per step, 4096 steps is 360°


# defining stepper motor sequence (found in documentation http://www.4tronix.co.uk/arduino/Stepper-Motors.php)
step_sequence = [[1, 0, 0, 1],
                 [1, 0, 0, 0],
                 [1, 1, 0, 0],
                 [0, 1, 0, 0],
                 [0, 1, 1, 0],
                 [0, 0, 1, 0],
                 [0, 0, 1, 1],
                 [0, 0, 0, 1]]


# setting up
GPIO.setmode(GPIO.BCM)
GPIO.setup(in1, GPIO.OUT)
GPIO.setup(in2, GPIO.OUT)
GPIO.setup(in3, GPIO.OUT)
GPIO.setup(in4, GPIO.OUT)

# initializing
GPIO.output(in1, GPIO.LOW)
GPIO.output(in2, GPIO.LOW)
GPIO.output(in3, GPIO.LOW)
GPIO.output(in4, GPIO.LOW)


GPIO.setup(M1_1, GPIO.OUT)
GPIO.setup(M1_2, GPIO.OUT)
GPIO.setup(M2_1, GPIO.OUT)
GPIO.setup(M2_2, GPIO.OUT)
GPIO.setup(en1, GPIO.OUT)
GPIO.setup(en2, GPIO.OUT)

pwm1 = GPIO.PWM(en1, 200)  # set frequency
pwm2 = GPIO.PWM(en2, 200)
pwm1.start(50)  # where dc is the duty cycle (0.0 <= dc <= 100.0)
pwm2.start(50)  # where dc is the duty cycle (0.0 <= dc <= 100.0)


app = Flask(__name__)  # set up flask server
# when the root IP is selected, return index.html page


@app.route('/')
def index():
    """Video streaming home page."""
    return render_template('index.html')


@app.route('/C_left_side')
def C_anticlockwise():
    motor_pins = [in1, in2, in3, in4]
    motor_step_counter = 0
    i = 0
    for i in range(step_count):
        for pin in range(0, len(motor_pins)):
            GPIO.output(motor_pins[pin],
                        step_sequence[motor_step_counter][pin])
        motor_step_counter = (motor_step_counter - 1) % 8
        time.sleep(step_sleep)
    return render_template('index.html')


@app.route('/C_right_side')
def C_clockwise():
    motor_pins = [in1, in2, in3, in4]
    motor_step_counter = 0
    i = 0
    for i in range(step_count):
        for pin in range(0, len(motor_pins)):
            GPIO.output(motor_pins[pin],
                        step_sequence[motor_step_counter][pin])
        motor_step_counter = (motor_step_counter + 1) % 8
        time.sleep(step_sleep)
    return render_template('index.html')


@app.route('/up_side')
def forward():
    dis = distance()
    if dis < 5:
        return render_template('index.html')
    if dis > 5:
        GPIO.output(M1_1, GPIO.HIGH)
        GPIO.output(M1_2, GPIO.LOW)
        GPIO.output(M2_1, GPIO.HIGH)
        GPIO.output(M2_2, GPIO.LOW)
        return render_template('index.html')


@app.route('/down_side')
def backward():
    GPIO.output(M1_1, GPIO.LOW)
    GPIO.output(M1_2, GPIO.HIGH)
    GPIO.output(M2_1, GPIO.LOW)
    GPIO.output(M2_2, GPIO.HIGH)
    return render_template('index.html')


@app.route('/right_side')
def right():
    GPIO.output(M2_1, GPIO.HIGH)
    GPIO.output(M2_2, GPIO.LOW)
    return render_template('index.html')


@app.route('/left_side')
def left():
    GPIO.output(M1_1, GPIO.HIGH)
    GPIO.output(M1_2, GPIO.LOW)
    return render_template('index.html')


@app.route('/stop')
def stop():
    GPIO.output(M1_1, GPIO.LOW)
    GPIO.output(M1_2, GPIO.LOW)
    GPIO.output(M2_1, GPIO.LOW)
    GPIO.output(M2_2, GPIO.LOW)
    return render_template('index.html')


@app.route('/speed1')
def speed1():
    pwm1.ChangeDutyCycle(50)
    pwm2.ChangeDutyCycle(50)
    return render_template('index.html')


@app.route('/speed2')
def speed2():
    pwm1.ChangeDutyCycle(75)
    pwm2.ChangeDutyCycle(75)
    return render_template('index.html')


@app.route('/speed3')
def speed3():
    pwm1.ChangeDutyCycle(100)
    pwm2.ChangeDutyCycle(100)
    return render_template('index.html')


@app.route('/video_feed')
def video_feed():
    # global cap
    return Response(main(), mimetype='multipart/x-mixed-replace; boundary=frame')


def distance():
    # set Trigger to HIGH
    GPIO.output(GPIO_TRIGGER, True)
    # set Trigger after 0.01ms to LOW
    time.sleep(0.00001)
    GPIO.output(GPIO_TRIGGER, False)
    StartTime = time.time()
    StopTime = time.time()
    # save StartTime
    while GPIO.input(GPIO_ECHO) == 0:
        StartTime = time.time()
    # save time of arrival
    while GPIO.input(GPIO_ECHO) == 1:
        StopTime = time.time()
    # time difference between start and arrival
    TimeElapsed = StopTime - StartTime
    # multiply with the sonic speed (34300 cm/s)
    # and divide by 2, because there and back
    distance = (TimeElapsed * 34300) / 2
    if distance > 255:
        return 255
    if distance < 255:
        return distance


def main():
    mdl = model
    font = cv2.FONT_HERSHEY_SIMPLEX
    interpreter, labels = cm.load_model(model_dir, mdl, lbl, 0)

    # while cap.isOpened():
    while True:

        # ----------------Capture Camera Frame-----------------
        ret, cv2_im = cap.read()
        if not ret:
            break

        cv2_im_rgb = cv2.cvtColor(cv2_im, cv2.COLOR_BGR2RGB)
        pil_im = Image.fromarray(cv2_im_rgb)

        # -------------------Inference---------------------------------
        cm.set_input(interpreter, pil_im)
        interpreter.invoke()
        objs = cm.get_output(
            interpreter, score_threshold=threshold, top_k=top_k)

        if len(objs) == 0:
            Odistance = distance()
            if (Odistance < 20):
                str_x = 'Obstacle distance is: {}'.format(Odistance)
                cv2_im = cv2.putText(
                    cv2_im, str_x, (10, 20), font, 0.7, (150, 150, 255), 2)
            ret, jpeg = cv2.imencode('.jpg', cv2_im)
            pic = jpeg.tobytes()

            # Flask streaming
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + pic + b'\r\n\r\n')

        if len(objs) > 0:
            for obj in objs:
                lbl_obj = labels.get(obj.id, obj.id)
                if (lbl_obj == object_to_track):
                    cv2_im = draw_overlays(cv2_im, objs, labels)
                    Odistance = distance()
                    if (Odistance < 20):
                        str_x = 'Obstacle distance is: {}'.format(Odistance)
                        cv2_im = cv2.putText(
                            cv2_im, str_x, (10, 20), font, 0.7, (150, 150, 255), 2)
                    ret, jpeg = cv2.imencode('.jpg', cv2_im)
                    pic = jpeg.tobytes()

                    # Flask streaming
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' + pic + b'\r\n\r\n')
                else:
                    Odistance = distance()
                    if (Odistance < 20):
                        str_x = 'Obstacle distance is: {}'.format(Odistance)
                        cv2_im = cv2.putText(
                            cv2_im, str_x, (10, 20), font, 0.7, (150, 150, 255), 2)
                    ret, jpeg = cv2.imencode('.jpg', cv2_im)
                    pic = jpeg.tobytes()

                    # Flask streaming
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' + pic + b'\r\n\r\n')

    cap.release()
    cv2.destroyAllWindows()


def draw_overlays(cv2_im, objs, labels):
    height, width, channels = cv2_im.shape
    font = cv2.FONT_HERSHEY_SIMPLEX
    # draw bounding boxes
    for obj in objs:
        x0, y0, x1, y1 = list(obj.bbox)
        x0, y0, x1, y1 = int(
            x0*width), int(y0*height), int(x1*width), int(y1*height)
        percent = int(100 * obj.score)

        box_color, text_color, thickness = (0, 150, 255), (0, 255, 0), 2
        cv2_im = cv2.rectangle(
            cv2_im, (x0, y0), (x1, y1), box_color, thickness)

        text = '{}% {}'.format(percent, labels.get(obj.id, obj.id))
        cv2_im = cv2.putText(cv2_im, text, (x0, y1-5),
                             font, 0.5, text_color, thickness)
    return cv2_im


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=2204, threaded=True)  # Run FLASK
    main()
