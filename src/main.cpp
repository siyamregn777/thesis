#ifndef LOW
#define LOW 0
#define HIGH 1
#endif

#include <Arduino.h> 
#include <Servo.h>

Servo gateServo;
bool gateOpen = false;
unsigned long gateOpenTime = 0;
const unsigned long GATE_OPEN_DURATION = 5000; // 5 seconds

const int triggerPin = 6;
const int echoPin = 7;
const int servoPin = 9;
const int detectionThreshold = 30;
bool systemEnabled = false; // Added system control flag

void setup() {
  pinMode(triggerPin, OUTPUT);
  pinMode(echoPin, INPUT);
  gateServo.attach(servoPin);
  Serial.begin(9600);
  gateServo.write(0); // Start closed
  Serial.println("System initialized");
}

long readUltrasonicDistance() {
  digitalWrite(triggerPin, LOW);
  delayMicroseconds(2);
  digitalWrite(triggerPin, HIGH);
  delayMicroseconds(10);
  digitalWrite(triggerPin, LOW);
  return pulseIn(echoPin, HIGH);
}

void loop() {
  // Handle serial commands from Python
  if (Serial.available() > 0) {
    String command = Serial.readStringUntil('\n');
    command.trim();
    
    if (command == "ENABLE") {
      systemEnabled = true;
      Serial.println("System enabled - Ready for plate recognition");
    } 
    else if (command == "DISABLE") {
      systemEnabled = false;
      gateServo.write(0); // Force close gate when disabled
      gateOpen = false;
      Serial.println("System disabled - Manual mode");
    }
    else if (command == "1" && systemEnabled && !gateOpen) {
      gateServo.write(120); // Open gate
      gateOpen = true;
      gateOpenTime = millis();
      Serial.println("Gate opened by command");
    } 
    else if (command == "0" && gateOpen) {
      gateServo.write(0); // Close gate
      gateOpen = false;
      Serial.println("Gate closed by command");
    }
  }

  // Auto-close after duration
  if (gateOpen && (millis() - gateOpenTime > GATE_OPEN_DURATION)) {
    gateServo.write(0);
    gateOpen = false;
    Serial.println("Gate auto-closed after timeout");
  }

  // Only use ultrasonic sensor when system is disabled
  if (!systemEnabled) {
    int distance = 0.01723 * readUltrasonicDistance();
    if (distance > 0 && distance < detectionThreshold) {
      if (!gateOpen) {
        gateServo.write(120);
        gateOpen = true;
        gateOpenTime = millis();
        Serial.println("Gate opened by sensor (manual mode)");
      }
    } else if (gateOpen && (millis() - gateOpenTime > GATE_OPEN_DURATION)) {
      gateServo.write(0);
      gateOpen = false;
      Serial.println("Gate auto-closed by sensor");
    }
  }

  delay(100); // Main loop delay
}