// ================================================
// ARVE - FIRMWARE COMPLETO v9.0 FINAL
// ================================================
// Componentes soportados (auto-detectados):
//   - Camara OV2640 (ESP32-CAM AI Thinker)
//   - PCA9685 (controla servos y motores)
//   - TB6612FNG (driver motores DC)
//   - 2 Servos SG90/TS90A (pan + tilt)
//   - HC-SR04 (sensor ultrasonico frontal)
//
// RED: por defecto usa DHCP (USE_DHCP=true). La IP la asigna el
//   hotspot/router y APARECE EN EL MONITOR SERIE al arrancar.
//   Usa ESA IP en arve_super_brain_v8.py / arve_viewer.py (--esp32-ip).
// Hostname: arve (tambien accesible como http://arve.local)
//
// Si el PCA9685 NO esta conectado: igual funciona
//   camara + WiFi. Cuando lo conectes, auto-detecta.
// ================================================
#include "esp_camera.h"
#include <WiFi.h>
#include <WebServer.h>
#include <Wire.h>
#include <Adafruit_PWMServoDriver.h>
#include <ESPmDNS.h>

// ================================================
// CONFIGURACION WIFI
// ================================================
const char* ssid     = "ARVE-07";
const char* password = "12345678";

// IP FIJA - siempre sera esta direccion!
IPAddress local_IP(192, 168, 137, 50);
IPAddress gateway(192, 168, 137, 1);
IPAddress subnet(255, 255, 255, 0);
IPAddress primaryDNS(8, 8, 8, 8);

// true  = DHCP (recomendado con hotspot de Windows; la IP sale en el Monitor Serie)
// false = IP fija (la de arriba); usala solo si tu router/hotspot lo permite
#define USE_DHCP true

// ================================================
// PINES FISICOS
// ================================================
#define I2C_SDA     14   // PCA9685 SDA
#define I2C_SCL     15   // PCA9685 SCL
#define TRIG_F      12   // HC-SR04 TRIG
#define ECHO_F      13   // HC-SR04 ECHO

#define CAMERA_MODEL_AI_THINKER
#include "camera_pins.h"

// Canales del PCA9685
#define M1_PWM      0
#define M1_IN1      1
#define M1_IN2      2
#define M2_PWM      3
#define M2_IN1      4
#define M2_IN2      5
#define CH_SERVO_PAN  6
#define CH_SERVO_TILT 7

// ================================================
// OBJETOS
// ================================================
WebServer server(80);
Adafruit_PWMServoDriver pwm = Adafruit_PWMServoDriver();
bool pca_available = false;

// ================================================
// VARIABLES DE ESTADO
// ================================================
int servo_pan = 90, servo_tilt = 90;
int vel_base = 1800, vel_giro = 1400;
int motor1_speed = 0, motor2_speed = 0;
bool modo_auto = false;
bool emergencia = false;
long dist_frontal = 100;
unsigned long t_ultrasonido = 0;
unsigned long t_auto = 0;

// Variables de IA (las envia Python)
float ai_x = 0.5f;
int ai_dist_cm = 0;
float ai_conf = 0.0f;
String ai_class = "";
unsigned long t_ai_ms = 0;
const unsigned long AI_TIMEOUT_MS = 1500;
const float AI_CONF_THRESHOLD = 0.50f;

// ================================================
// CONTROL DE HARDWARE (con auto-detect)
// ================================================
int angulo_a_pwm(int angulo) {
  return map(angulo, 0, 180, 102, 512);
}

void setServoPan(int angulo) {
  servo_pan = constrain(angulo, 0, 180);
  if (pca_available) pwm.setPWM(CH_SERVO_PAN, 0, angulo_a_pwm(servo_pan));
}

void setServoTilt(int angulo) {
  servo_tilt = constrain(angulo, 0, 180);
  if (pca_available) pwm.setPWM(CH_SERVO_TILT, 0, angulo_a_pwm(servo_tilt));
}

void setMotor(int m, int speed) {
  if (emergencia && speed > 0) speed = 0;
  if (m == 1) motor1_speed = speed;
  else        motor2_speed = speed;
  if (!pca_available) return;
  int ch_pwm = (m == 1) ? M1_PWM : M2_PWM;
  int in1    = (m == 1) ? M1_IN1 : M2_IN1;
  int in2    = (m == 1) ? M1_IN2 : M2_IN2;
  speed = constrain(speed, -4095, 4095);
  if (speed > 0) {
    pwm.setPWM(in1, 4095, 0);
    pwm.setPWM(in2, 0, 4095);
    pwm.setPWM(ch_pwm, 0, speed);
  } else if (speed < 0) {
    pwm.setPWM(in1, 0, 4095);
    pwm.setPWM(in2, 4095, 0);
    pwm.setPWM(ch_pwm, 0, abs(speed));
  } else {
    pwm.setPWM(in1, 0, 4095);
    pwm.setPWM(in2, 0, 4095);
    pwm.setPWM(ch_pwm, 0, 0);
  }
}

long medir_distancia() {
  digitalWrite(TRIG_F, LOW); delayMicroseconds(2);
  digitalWrite(TRIG_F, HIGH); delayMicroseconds(10);
  digitalWrite(TRIG_F, LOW);
  unsigned long dur = pulseIn(ECHO_F, HIGH, 8000);
  if (dur == 0) return -1;
  return (long)(dur * 0.0343f / 2.0f);
}

// ================================================
// STREAM MJPEG (PROBADO QUE FUNCIONA)
// ================================================
#define PART_BOUNDARY "arve"
static const char* STREAM_CT = "multipart/x-mixed-replace;boundary=" PART_BOUNDARY;
static const char* STREAM_BD = "\r\n--" PART_BOUNDARY "\r\n";
static const char* STREAM_PT = "Content-Type: image/jpeg\r\nContent-Length: %u\r\n\r\n";

void stream_task(void *pv) {
  WiFiServer s(81);
  s.begin();
  while (1) {
    WiFiClient c = s.available();
    if (c) {
      c.setNoDelay(true);
      c.printf("HTTP/1.1 200 OK\r\nContent-Type: %s\r\n\r\n", STREAM_CT);
      while (c.connected()) {
        camera_fb_t* fb = esp_camera_fb_get();
        if (!fb) { delay(5); continue; }
        c.write(STREAM_BD, strlen(STREAM_BD));
        char hdr[64];
        int hlen = snprintf(hdr, sizeof(hdr), STREAM_PT, fb->len);
        c.write((const uint8_t*)hdr, hlen);
        c.write(fb->buf, fb->len);
        esp_camera_fb_return(fb);
        delay(15);
      }
      c.stop();
    }
    delay(50);
  }
}

// ================================================
// RUTAS HTTP
// ================================================
void handle_root() {
  String ip = WiFi.localIP().toString();
  String h = "<!doctype html><html><head><meta charset='utf-8'>"
             "<title>ARVE</title>"
             "<style>body{font-family:Arial;background:#101418;color:#e6e6e6;text-align:center;padding:12px}"
             "img{max-width:100%;border:2px solid #2b3038;border-radius:8px}"
             "a{color:#6ab0ff}</style></head><body>"
             "<h2>ARVE ONLINE</h2>"
             "<p>IP: " + ip + "</p>"
             "<p>Stream: <a href='http://" + ip + ":81' target='_blank'>http://" + ip + ":81</a></p>"
             "<p><i>(No abrir el stream aqui si vas a usar Python)</i></p>"
             "</body></html>";
  server.send(200, "text/html", h);
}

void handle_move() {
  setMotor(1, server.arg("v1").toInt());
  setMotor(2, server.arg("v2").toInt());
  Serial.printf("[MOTOR] v1=%d v2=%d\n", motor1_speed, motor2_speed);
  server.send(200, "text/plain", "OK");
}

void handle_servo() {
  if (server.hasArg("ang")) setServoPan(server.arg("ang").toInt());
  server.send(200, "text/plain", "OK");
}

void handle_servo2() {
  if (server.hasArg("ang")) setServoTilt(server.arg("ang").toInt());
  server.send(200, "text/plain", "OK");
}

void handle_mode() {
  String m = server.arg("m"); m.toLowerCase();
  modo_auto = (m == "auto");
  if (!modo_auto) { setMotor(1, 0); setMotor(2, 0); }
  Serial.printf("[MODO] %s\n", modo_auto ? "AUTO" : "MANUAL");
  server.send(200, "text/plain", "OK");
}

void handle_speed() {
  if (server.hasArg("base")) vel_base = constrain(server.arg("base").toInt(), 500, 4095);
  if (server.hasArg("turn")) vel_giro = constrain(server.arg("turn").toInt(), 500, 4095);
  server.send(200, "text/plain", "OK");
}

void handle_ai() {
  if (server.hasArg("x"))    ai_x = server.arg("x").toFloat();
  if (server.hasArg("dist")) ai_dist_cm = server.arg("dist").toInt();
  if (server.hasArg("conf")) ai_conf = server.arg("conf").toFloat();
  if (server.hasArg("cls"))  ai_class = server.arg("cls");
  t_ai_ms = millis();
  server.send(200, "text/plain", "OK");
}

void handle_status() {
  String j = "{";
  j += "\"pca\":" + String(pca_available ? "true" : "false") + ",";
  j += "\"dist_f\":" + String(dist_frontal > 0 ? dist_frontal : 0) + ",";
  j += "\"emergencia\":" + String(emergencia ? "true" : "false") + ",";
  j += "\"servo_pan\":" + String(servo_pan) + ",";
  j += "\"servo_tilt\":" + String(servo_tilt) + ",";
  j += "\"motor1\":" + String(motor1_speed) + ",";
  j += "\"motor2\":" + String(motor2_speed) + ",";
  j += "\"modo_auto\":" + String(modo_auto ? "true" : "false") + ",";
  j += "\"velocidad_base\":" + String(vel_base) + ",";
  j += "\"ai_x\":" + String(ai_x, 3) + ",";
  j += "\"ai_dist_cm\":" + String(ai_dist_cm) + ",";
  j += "\"ai_conf\":" + String(ai_conf, 3) + ",";
  j += "\"ai_class\":\"" + ai_class + "\"";
  j += "}";
  server.send(200, "application/json", j);
}

void handle_res() {
  if (!server.hasArg("s")) { server.send(400, "text/plain", "falta s"); return; }
  String s = server.arg("s"); s.toLowerCase();
  sensor_t* sen = esp_camera_sensor_get();
  if (!sen) { server.send(500, "text/plain", "sin sensor"); return; }
  framesize_t fs = FRAMESIZE_QVGA;
  if      (s == "qqvga") fs = FRAMESIZE_QQVGA;
  else if (s == "qvga")  fs = FRAMESIZE_QVGA;
  else if (s == "hvga")  fs = FRAMESIZE_HVGA;
  else if (s == "vga")   fs = FRAMESIZE_VGA;
  sen->set_framesize(sen, fs);
  server.send(200, "text/plain", "OK");
}

void handle_quality() {
  if (!server.hasArg("q")) { server.send(400, "text/plain", "falta q"); return; }
  int q = constrain(server.arg("q").toInt(), 5, 60);
  sensor_t* sen = esp_camera_sensor_get();
  if (sen) sen->set_quality(sen, q);
  server.send(200, "text/plain", "OK");
}

// ================================================
// SETUP
// ================================================
#include "soc/soc.h"
#include "soc/rtc_cntl_reg.h"

void setup() {
  WRITE_PERI_REG(RTC_CNTL_BROWN_OUT_REG, 0);

  Serial.begin(115200);
  delay(1500);
  Serial.println("\n=========================");
  Serial.println("  ARVE v9.0 ARRANCANDO");
  Serial.println("=========================");

  bool psram = psramFound();
  Serial.printf("[INFO] PSRAM: %s\n", psram ? "SI" : "NO");

  // Pines del sensor ultrasonico HC-SR04
  pinMode(TRIG_F, OUTPUT);
  pinMode(ECHO_F, INPUT);
  Serial.println("[OK] Pines HC-SR04 listos");

  // I2C + PCA9685 (auto-detect)
  Wire.begin(I2C_SDA, I2C_SCL);
  Wire.setClock(100000);
  Wire.setTimeOut(50);
  Serial.println("[..] Buscando PCA9685...");
  pca_available = pwm.begin();
  if (pca_available) {
    pwm.setPWMFreq(50);
    Serial.println("[OK] PCA9685 detectado - motores/servos activos");
    setServoPan(90);
    setServoTilt(90);
  } else {
    Serial.println("[INFO] PCA9685 no detectado - modo solo camara/WiFi");
  }

  // Camara
  camera_config_t cfg = {};
  cfg.ledc_channel = LEDC_CHANNEL_0;
  cfg.ledc_timer   = LEDC_TIMER_0;
  cfg.pin_d0 = Y2_GPIO_NUM; cfg.pin_d1 = Y3_GPIO_NUM;
  cfg.pin_d2 = Y4_GPIO_NUM; cfg.pin_d3 = Y5_GPIO_NUM;
  cfg.pin_d4 = Y6_GPIO_NUM; cfg.pin_d5 = Y7_GPIO_NUM;
  cfg.pin_d6 = Y8_GPIO_NUM; cfg.pin_d7 = Y9_GPIO_NUM;
  cfg.pin_xclk = XCLK_GPIO_NUM; cfg.pin_pclk = PCLK_GPIO_NUM;
  cfg.pin_vsync = VSYNC_GPIO_NUM; cfg.pin_href = HREF_GPIO_NUM;
  cfg.pin_sscb_sda = SIOD_GPIO_NUM; cfg.pin_sscb_scl = SIOC_GPIO_NUM;
  cfg.pin_pwdn = PWDN_GPIO_NUM; cfg.pin_reset = RESET_GPIO_NUM;
  cfg.xclk_freq_hz = 20000000;
  cfg.pixel_format = PIXFORMAT_JPEG;
  cfg.grab_mode    = CAMERA_GRAB_LATEST;
  if (psram) {
    cfg.frame_size   = FRAMESIZE_QVGA;
    cfg.jpeg_quality = 12;
    cfg.fb_count     = 2;
    cfg.fb_location  = CAMERA_FB_IN_PSRAM;
  } else {
    cfg.frame_size   = FRAMESIZE_QCIF;
    cfg.jpeg_quality = 25;
    cfg.fb_count     = 1;
    cfg.fb_location  = CAMERA_FB_IN_DRAM;
  }
  if (esp_camera_init(&cfg) != ESP_OK) {
    Serial.println("[ERROR] camara fallo");
    while (1) delay(100);
  }
  sensor_t* s = esp_camera_sensor_get();
  if (s) {
    s->set_brightness(s, 1);
    s->set_contrast(s, 1);
    s->set_whitebal(s, 1);
  }
  Serial.println("[OK] camara");

  // WiFi
  WiFi.mode(WIFI_STA);
  WiFi.setSleep(false);
  if (!USE_DHCP) {
    if (!WiFi.config(local_IP, gateway, subnet, primaryDNS)) {
      Serial.println("[WARN] IP fija fallo, usando DHCP");
    } else {
      Serial.println("[INFO] Usando IP fija");
    }
  } else {
    Serial.println("[INFO] Usando DHCP (IP automatica)");
  }
  Serial.printf("[..] Conectando a %s ", ssid);
  int tries = 0;
  while (WiFi.status() != WL_CONNECTED && tries < 3) {
    WiFi.begin(ssid, password);
    unsigned long t0 = millis();
    while (WiFi.status() != WL_CONNECTED && millis() - t0 < 20000) {
      delay(400);
      Serial.print(".");
    }
    if (WiFi.status() != WL_CONNECTED) {
      tries++;
      Serial.printf("\n[..] Reintento %d/3\n", tries);
      WiFi.disconnect(true);
      delay(500);
    }
  }
  Serial.println();
  if (WiFi.status() == WL_CONNECTED) {
    Serial.printf("[OK] IP: %s\n", WiFi.localIP().toString().c_str());
    Serial.printf("[OK] http://%s\n", WiFi.localIP().toString().c_str());
    Serial.printf("[OK] stream http://%s:81\n", WiFi.localIP().toString().c_str());
    Serial.printf("[OK] RSSI: %d dBm\n", WiFi.RSSI());

    // mDNS (acceso por nombre: http://arve.local)
    if (MDNS.begin("arve")) {
      Serial.println("[OK] mDNS activo: http://arve.local");
    }
  } else {
    Serial.println("[ERROR] WiFi fallo - revisa hotspot");
  }

  xTaskCreatePinnedToCore(stream_task, "stream", 8192, NULL, 1, NULL, 0);

  server.on("/",        handle_root);
  server.on("/move",    handle_move);
  server.on("/servo",   handle_servo);
  server.on("/servo2",  handle_servo2);
  server.on("/mode",    handle_mode);
  server.on("/speed",   handle_speed);
  server.on("/ai",      handle_ai);
  server.on("/status",  handle_status);
  server.on("/res",     handle_res);
  server.on("/quality", handle_quality);
  server.begin();
  Serial.println("[OK] HTTP listo - SISTEMA OPERATIVO");
}

// ================================================
// LOOP - logica del robot
// ================================================
void loop() {
  server.handleClient();

  unsigned long ahora = millis();

  // Sensor ultrasonico cada 100ms
  if (ahora - t_ultrasonido >= 100) {
    t_ultrasonido = ahora;
    dist_frontal = medir_distancia();
    if (dist_frontal > 0 && dist_frontal < 20) {
      if (!emergencia) {
        emergencia = true;
        setMotor(1, 0); setMotor(2, 0);
        Serial.println("[!] EMERGENCIA: OBSTACULO");
      }
    } else {
      if (emergencia) {
        emergencia = false;
      }
    }
  }

  // Logica modo automatico
  if (modo_auto && (ahora - t_auto >= 150)) {
    t_auto = ahora;
    bool ai_activa = (ahora - t_ai_ms) < AI_TIMEOUT_MS &&
                     ai_conf >= AI_CONF_THRESHOLD;

    bool obstaculo = (dist_frontal > 0 && dist_frontal < 22);
    if (obstaculo) {
      // Hay obstaculo: girar para evitar
      setMotor(1, -vel_giro);
      setMotor(2,  vel_giro);
      return;
    }

    if (ai_activa) {
      // IA detecto algo: perseguir
      if (ai_x < 0.40f) {
        // Esta a la izquierda
        setMotor(1, -vel_giro);
        setMotor(2,  vel_giro);
      } else if (ai_x > 0.60f) {
        // Esta a la derecha
        setMotor(1,  vel_giro);
        setMotor(2, -vel_giro);
      } else {
        // Centrado: avanzar
        int v = vel_base;
        if (ai_dist_cm > 0 && ai_dist_cm < 20) v = vel_base / 2;
        setMotor(1, v);
        setMotor(2, v);
      }
    } else {
      // No detecto nada: girar lento buscando
      setMotor(1, -vel_giro / 2);
      setMotor(2,  vel_giro / 2);
    }
  }
}
