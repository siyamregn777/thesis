// #include <Firmata.h>

// void setup() {
//     Firmata.begin(57600);
//     pinMode(13, OUTPUT); // Pin for gate control
//     pinMode(12, OUTPUT); // Pin for alert system
// }

// void loop() {
//     if (Firmata.available()) {
//         int command = Firmata.read();
//         if (command == 1) {
//             digitalWrite(13, HIGH); // Open gate
//             delay(5000); // Keep it open for 5 seconds
//             digitalWrite(13, LOW);
//         } else if (command == 2) {
//             digitalWrite(12, HIGH); // Trigger alert
//             delay(3000);
//             digitalWrite(12, LOW);
//         }
//     }
// }