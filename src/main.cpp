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
const int servoPin = 9;

void setup() {
  gateServo.attach(servoPin);
  Serial.begin(9600);
  gateServo.write(0); // Start closed
  Serial.println("READY"); // Simple ready message
}

void loop() {
  // Handle serial commands
  if (Serial.available() > 0) {
    char command = Serial.read();
    
    if (command == '1' && !gateOpen) {
      gateServo.write(120); // Open gate
      gateOpen = true;
      gateOpenTime = millis();
      Serial.println("OPENED");
    } 
    else if (command == '0' && gateOpen) {
      gateServo.write(0); // Close gate
      gateOpen = false;
      Serial.println("CLOSED");
    }
  }

  // Auto-close after duration
  if (gateOpen && (millis() - gateOpenTime > GATE_OPEN_DURATION)) {
    gateServo.write(0);
    gateOpen = false;
    Serial.println("AUTO_CLOSED");
  }

  delay(50); // Reduced delay for better responsiveness
}