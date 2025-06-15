#include <Servo.h>
Servo myservo;

int cm = 0;
bool isOpen = false;
unsigned long lastDetectionTime = 0;
const int triggerPin = 6;
const int echoPin = 7;
const int servoPin = 9;

const int detectionThreshold = 30; // cm
const int holdTime = 2000;         // ms

long readUltrasonicDistance(int triggerPin, int echoPin) {
  digitalWrite(triggerPin, LOW);
  delayMicroseconds(2);
  digitalWrite(triggerPin, HIGH);
  delayMicroseconds(10);
  digitalWrite(triggerPin, LOW);
  return pulseIn(echoPin, HIGH);
}

void setup() {
  pinMode(triggerPin, OUTPUT);
  pinMode(echoPin, INPUT);
  myservo.attach(servoPin);
  Serial.begin(9600);
  myservo.write(0); // Initially closed
}

void loop() {
  cm = 0.01723 * readUltrasonicDistance(triggerPin, echoPin);
  Serial.print(cm);
  Serial.println(" cm");

  unsigned long currentTime = millis();

  if (cm > 0 && cm < detectionThreshold) {
    lastDetectionTime = currentTime;
    if (!isOpen) {
      myservo.write(120); // Open
      isOpen = true;
    }
  } else {
    if (isOpen && (currentTime - lastDetectionTime > holdTime)) {
      myservo.write(0); // Close
      isOpen = false;
    }
  }

  delay(100); // Sensor stability
}