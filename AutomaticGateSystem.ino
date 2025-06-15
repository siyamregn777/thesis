#include <Servo.h>
#include <Wire.h>

// Pin definitions
const int trigPin = 9;
const int echoPin = 10;
const int servoPin = 11;
const int ledPin = 13; // Status LED
const int gateOpenPin = 7; // Output to indicate gate should open
const int gateClosePin = 8; // Output to indicate gate should close

// Gate parameters
const int GATE_OPEN_ANGLE = 90;
const int GATE_CLOSED_ANGLE = 0;
const int MIN_DISTANCE_CM = 30; // Distance to detect vehicle presence

Servo gateServo;
bool gateOpen = false;
unsigned long lastDetectionTime = 0;
const unsigned long GATE_CLOSE_DELAY = 10000; // 10 seconds delay before closing gate

void setup() {
  Serial.begin(9600);
  
  // Initialize pins
  pinMode(trigPin, OUTPUT);
  pinMode(echoPin, INPUT);
  pinMode(ledPin, OUTPUT);
  pinMode(gateOpenPin, OUTPUT);
  pinMode(gateClosePin, OUTPUT);
  
  gateServo.attach(servoPin);
  closeGate(); // Start with gate closed
  
  // Wait for serial connection (for debugging)
  while (!Serial) {
    delay(10);
  }
  
  Serial.println("Automatic Gate System Ready");
}

void loop() {
  // Check for vehicle presence
  int distance = getDistance();
  
  if (distance <= MIN_DISTANCE_CM) {
    Serial.println("Vehicle detected - Checking license plate...");
    digitalWrite(ledPin, HIGH); // Turn on status LED
    
    // Send signal to PC to process image
    Serial.println("CAPTURE"); // This tells Python to capture and process image
    
    // Wait for response from PC
    waitForResponse();
    
    lastDetectionTime = millis();
  }
  
  // Auto-close gate if no vehicle detected for specified time
  if (gateOpen && (millis() - lastDetectionTime) > GATE_CLOSE_DELAY) {
    closeGate();
    Serial.println("Auto-closing gate after delay");
  }
  
  delay(500); // Short delay between checks
}

void waitForResponse() {
  unsigned long startTime = millis();
  const unsigned long timeout = 30000; // 30 second timeout
  
  while (millis() - startTime < timeout) {
    if (Serial.available() > 0) {
      String response = Serial.readStringUntil('\n');
      response.trim();
      
      if (response == "OPEN") {
        openGate();
        return;
      } else if (response == "CLOSE") {
        closeGate();
        return;
      } else if (response == "NO_PLATE") {
        Serial.println("No license plate detected");
        digitalWrite(ledPin, LOW);
        return;
      }
    }
    delay(100);
  }
  
  Serial.println("Timeout waiting for response");
  digitalWrite(ledPin, LOW);
}

int getDistance() {
  digitalWrite(trigPin, LOW);
  delayMicroseconds(2);
  digitalWrite(trigPin, HIGH);
  delayMicroseconds(10);
  digitalWrite(trigPin, LOW);
  
  long duration = pulseIn(echoPin, HIGH);
  int distance = duration * 0.034 / 2;
  
  Serial.print("Distance: ");
  Serial.print(distance);
  Serial.println(" cm");
  
  return distance;
}

void openGate() {
  if (!gateOpen) {
    gateServo.write(GATE_OPEN_ANGLE);
    digitalWrite(gateOpenPin, HIGH);
    digitalWrite(gateClosePin, LOW);
    gateOpen = true;
    Serial.println("Gate opened");
    delay(1000); // Allow time for gate to open
    digitalWrite(gateOpenPin, LOW); // Turn off signal after operation
  }
}

void closeGate() {
  if (gateOpen) {
    gateServo.write(GATE_CLOSED_ANGLE);
    digitalWrite(gateClosePin, HIGH);
    digitalWrite(gateOpenPin, LOW);
    gateOpen = false;
    Serial.println("Gate closed");
    delay(1000); // Allow time for gate to close
    digitalWrite(gateClosePin, LOW); // Turn off signal after operation
  }
}