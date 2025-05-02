#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>

const char* ssid = "Wokwi-GUEST";
const char* password = "";
const char* flask_server = "http://localhost:5000/check_plate?plate=";

const int ledGrantedPin = 12;  // Green LED
const int ledDeniedPin = 14;   // Red LED

void setup() {
  Serial.begin(115200);
  pinMode(ledGrantedPin, OUTPUT);
  pinMode(ledDeniedPin, OUTPUT);
  
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nConnected to WiFi!");
}

void loop() {
  // Reset LEDs
  digitalWrite(ledGrantedPin, LOW);
  digitalWrite(ledDeniedPin, LOW);

  // Handle WiFi disconnection
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("WiFi disconnected - reconnecting...");
    WiFi.reconnect();
    while (WiFi.status() != WL_CONNECTED) {
      delay(500);
      Serial.print(".");
    }
    Serial.println("\nReconnected!");
  }

  if (Serial.available()) {
    String plate = Serial.readStringUntil('\n');
    plate.trim();
    
    if (plate.length() > 0) {
      Serial.println("Checking plate: " + plate);
      
      HTTPClient http;
      http.begin(flask_server + plate);
      http.setTimeout(5000);
      
      int httpCode = http.GET();
      
      if (httpCode == 200) {
        String payload = http.getString();
        DynamicJsonDocument doc(1024);
        deserializeJson(doc, payload);
        
        if (doc["registered"] == true) {
          Serial.println("Access Granted");
          digitalWrite(ledGrantedPin, HIGH);
        } else {
          Serial.println("Access Denied");
          digitalWrite(ledDeniedPin, HIGH);
        }
      } else {
        Serial.printf("HTTP Error: %d\n", httpCode);
        // Error blink pattern
        for(int i=0; i<3; i++) {
          digitalWrite(ledDeniedPin, HIGH);
          delay(200);
          digitalWrite(ledDeniedPin, LOW);
          delay(200);
        }
      }
      http.end();
    }
  }
  delay(100);
}