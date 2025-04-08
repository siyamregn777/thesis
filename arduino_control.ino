// #include <Servo.h>

// Servo gateServo;  // Create servo object
// int pos = 0;      // Servo position
// bool gateState = false;

// void setup() {
//   Serial.begin(9600);
//   gateServo.attach(9);  // Servo on pin 9
//   closeGate();          // Initialize gate closed
// }

// void loop() {
//   if (Serial.available() > 0) {
//     char command = Serial.read();
    
//     if (command == 'O') {
//       openGate();
//     } 
//     else if (command == 'C') {
//       closeGate();
//     }
//   }
// }

// void openGate() {
//   if (!gateState) {
//     for (pos = 0; pos <= 90; pos += 1) {
//       gateServo.write(pos);
//       delay(15);
//     }
//     gateState = true;
//     Serial.println("Gate opened");
//   }
// }

// void closeGate() {
//   if (gateState) {
//     for (pos = 90; pos >= 0; pos -= 1) {
//       gateServo.write(pos);
//       delay(15);
//     }
//     gateState = false;
//     Serial.println("Gate closed");
//   }
// }