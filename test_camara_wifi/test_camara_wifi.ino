// ================================================
// TEST CAMARA + WIFI - ESP32-CAM AI Thinker
// Version minima para probar solo la camara y la red.
// Sin PCA9685, sin motores, sin sensores, sin buzzer.
//
// Como usar:
//   1) Cambia ssid y password abajo.
//   2) Selecciona Placa: "AI Thinker ESP32-CAM"
//   3) Particion: "Huge APP (3MB No OTA/1MB SPIFFS)"
//   4) Sube con GPIO0 a GND, luego desconecta GPIO0 y RESET.
//   5) Abre el monitor serie a 115200 baudios y copia la IP.
//   6) Abre esa IP en el navegador.
// ================================================
#include "esp_camera.h"
#include <WiFi.h>
#include <WebServer.h>

// --- CAMBIA AQUI TUS DATOS WIFI ---
const char* ssid     = "ARVE-07";
const char* password = "12345678";

// Modelo de camara
#define CAMERA_MODEL_AI_THINKER
#include "camera_pins.h"

WebServer server(80);

// ================================================
// STREAM MJPEG en el puerto 81
// ================================================
#define PART_BOUNDARY "arvelimit"
static const char* STREAM_CT = "multipart/x-mixed-replace;boundary=" PART_BOUNDARY;
static const char* STREAM_BD = "\r\n--" PART_BOUNDARY "\r\n";
static const char* STREAM_PT = "Content-Type: image/jpeg\r\nContent-Length: %u\r\n\r\n";

void stream_task(void *pvParameters) {
  static WiFiServer stream_server(81);
  stream_server.begin();
  while (1) {
    WiFiClient client = stream_server.available();
    if (client) {
      client.setNoDelay(true);
      client.printf("HTTP/1.1 200 OK\r\nContent-Type: %s\r\n\r\n", STREAM_CT);
      while (client.connected()) {
        camera_fb_t* fb = esp_camera_fb_get();
        if (!fb) {
          delay(5);
          continue;
        }
        client.write(STREAM_BD, strlen(STREAM_BD));
        client.printf(STREAM_PT, fb->len);
        client.write(fb->buf, fb->len);
        esp_camera_fb_return(fb);
        delay(15);
      }
      client.stop();
    }
    delay(50);
  }
}

// ================================================
// Pagina HTML simple con la imagen del stream
// ================================================
void handle_root() {
  String ip = WiFi.localIP().toString();
  String html = "<!doctype html><html><head><meta charset='utf-8'>";
  html += "<meta name='viewport' content='width=device-width,initial-scale=1'>";
  html += "<title>ESP32-CAM Test</title>";
  html += "<style>body{font-family:Arial;text-align:center;background:#101418;color:#e6e6e6;margin:0;padding:16px;}";
  html += "img{max-width:100%;border:2px solid #2b3038;border-radius:8px;}";
  html += "h2{margin:8px;} p{color:#6ab0ff;}</style></head><body>";
  html += "<h2>ESP32-CAM TEST OK</h2>";
  html += "<p>IP: " + ip + "</p>";
  html += "<img src='http://" + ip + ":81' alt='stream'>";
  html += "</body></html>";
  server.send(200, "text/html", html);
}

// ================================================
// Captura una sola foto JPEG
// ================================================
void handle_capture() {
  camera_fb_t* fb = esp_camera_fb_get();
  if (!fb) {
    server.send(500, "text/plain", "Error al capturar");
    return;
  }
  server.sendHeader("Content-Type", "image/jpeg");
  server.sendHeader("Content-Disposition", "inline; filename=capture.jpg");
  server.sendHeader("Connection", "close");
  server.send_P(200, "image/jpeg", (const char*)fb->buf, fb->len);
  esp_camera_fb_return(fb);
}

// ================================================
// SETUP
// ================================================
#include "soc/soc.h"
#include "soc/rtc_cntl_reg.h"

void setup() {
  WRITE_PERI_REG(RTC_CNTL_BROWN_OUT_REG, 0); // Evita reinicios por brownout

  Serial.begin(115200);
  delay(2000);
  Serial.println("\n\n====================================");
  Serial.println("--- ESP32-CAM TEST CAMARA + WIFI ---");
  Serial.println("====================================\n");

  bool has_psram = psramFound();
  if (has_psram) {
    Serial.printf("[INFO] PSRAM detectada: %d bytes\n", ESP.getPsramSize());
  } else {
    Serial.println("[WARN] Sin PSRAM - usando modo bajo consumo");
  }
  Serial.printf("[INFO] RAM libre: %d bytes\n", ESP.getFreeHeap());

  // Configuracion de la camara
  camera_config_t config = {};
  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer   = LEDC_TIMER_0;
  config.pin_d0 = Y2_GPIO_NUM; config.pin_d1 = Y3_GPIO_NUM;
  config.pin_d2 = Y4_GPIO_NUM; config.pin_d3 = Y5_GPIO_NUM;
  config.pin_d4 = Y6_GPIO_NUM; config.pin_d5 = Y7_GPIO_NUM;
  config.pin_d6 = Y8_GPIO_NUM; config.pin_d7 = Y9_GPIO_NUM;
  config.pin_xclk = XCLK_GPIO_NUM; config.pin_pclk = PCLK_GPIO_NUM;
  config.pin_vsync = VSYNC_GPIO_NUM; config.pin_href = HREF_GPIO_NUM;
  config.pin_sscb_sda = SIOD_GPIO_NUM; config.pin_sscb_scl = SIOC_GPIO_NUM;
  config.pin_pwdn = PWDN_GPIO_NUM; config.pin_reset = RESET_GPIO_NUM;
  config.xclk_freq_hz = 20000000;
  config.pixel_format = PIXFORMAT_JPEG;
  config.grab_mode    = CAMERA_GRAB_LATEST;

  if (has_psram) {
    config.frame_size   = FRAMESIZE_VGA;     // 640x480
    config.jpeg_quality = 12;
    config.fb_count     = 2;
    config.fb_location  = CAMERA_FB_IN_PSRAM;
  } else {
    config.frame_size   = FRAMESIZE_QVGA;    // 320x240
    config.jpeg_quality = 20;
    config.fb_count     = 1;
    config.fb_location  = CAMERA_FB_IN_DRAM;
  }

  Serial.println("[DEBUG] Inicializando camara...");
  esp_err_t err = esp_camera_init(&config);
  if (err != ESP_OK) {
    Serial.printf("[ERROR] Camara fallo, codigo: 0x%x\n", err);
    while (true) { delay(1000); }
  }
  Serial.println("[OK] Camara inicializada");

  // Ajustes basicos del sensor
  sensor_t* s = esp_camera_sensor_get();
  if (s) {
    s->set_brightness(s, 1);
    s->set_contrast(s, 1);
    s->set_saturation(s, 0);
    s->set_gain_ctrl(s, 1);
    s->set_exposure_ctrl(s, 1);
    s->set_whitebal(s, 1);
    s->set_awb_gain(s, 1);
  }

  // WiFi
  Serial.printf("[INFO] Conectando a %s ", ssid);
  WiFi.mode(WIFI_STA);
  WiFi.setSleep(false);
  WiFi.begin(ssid, password);

  unsigned long t0 = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - t0 < 20000) {
    delay(500);
    Serial.print(".");
  }

  if (WiFi.status() == WL_CONNECTED) {
    Serial.println();
    Serial.printf("[OK] WiFi conectado\n");
    Serial.printf("[IP] http://%s\n", WiFi.localIP().toString().c_str());
    Serial.printf("[STREAM] http://%s:81\n", WiFi.localIP().toString().c_str());
  } else {
    Serial.println("\n[ERROR] No se pudo conectar al WiFi");
    Serial.println("        Verifica ssid/password y vuelve a intentar.");
  }

  // Tarea del stream en el otro core
  xTaskCreatePinnedToCore(stream_task, "stream_task", 8192, NULL, 1, NULL, 0);

  // Rutas HTTP
  server.on("/",        handle_root);
  server.on("/capture", handle_capture);
  server.begin();
  Serial.println("[OK] Servidor HTTP listo en puerto 80");
}

// ================================================
// LOOP
// ================================================
void loop() {
  server.handleClient();
  delay(2);
}
