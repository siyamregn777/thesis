#include <Arduino.h> 
#include <Servo.h>

Servo gateServo;
bool gateOpen = false;
const unsigned long GATE_OPEN_DURATION = 10000; // 10 seconds

// Ultrasonic sensor pins
const int triggerPin = 6;
const int echoPin = 7;
const int servoPin = 9;
const int detectionThreshold = 30; // 30cm detection range

void setup() {
  pinMode(triggerPin, OUTPUT);
  pinMode(echoPin, INPUT);
  gateServo.attach(servoPin);
  Serial.begin(9600);
  gateServo.write(0); // Start with gate closed
  Serial.println("READY");
}

long getDistance() {
  digitalWrite(triggerPin, LOW);
  delayMicroseconds(2);
  digitalWrite(triggerPin, HIGH);
  delayMicroseconds(10);
  digitalWrite(triggerPin, LOW);
  return pulseIn(echoPin, HIGH) * 0.034 / 2; // Convert to cm
}

void closeGate() {
  gateServo.write(0); // Close gate
  gateOpen = false;
  Serial.println("CLOSED");
}

void openGate() {
  gateServo.write(120); // Open gate
  gateOpen = true;
  Serial.println("OPENED");
  delay(GATE_OPEN_DURATION); 
  closeGate(); // Close gate after duration
}

void loop() {
  // Automatic ultrasonic detection
  int distance = getDistance();
  if (distance > 0 && distance < detectionThreshold && !gateOpen) {
    Serial.println("DETECTED"); // Send detection signal to Python
    delay(1000); // Debounce delay
  }

  // Handle serial commands from Python
  if (Serial.available() > 0) {
    char command = Serial.read();
    
    if (command == '1' && !gateOpen) {
      openGate();
    } 
    else if (command == '0') {
      closeGate();
    }
  }

  delay(100);
}