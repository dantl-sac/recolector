// ================================================
// ARVE ELITE - FIRMWARE DEFINITIVO v5.0
// Componentes: ESP32-CAM, TB6612FNG, PCA9685,
//              HC-SR04 x2, Servo SG90, TCS3200,
//              LED RGB x3, Buzzer 5V
// ================================================
#include "esp_camera.h"
#include <WiFi.h>
#include <WebServer.h>
#include <Wire.h>
#include <Adafruit_PWMServoDriver.h>

// --- RED ---
const char* ssid = "ARVE-07"; 
const char* password = "12345678";
IPAddress local_IP(192, 168, 137, 100);
IPAddress gateway(192, 168, 137, 1);
IPAddress subnet(255, 255, 255, 0);

// ================================================
// PINES FÍSICOS DEL ESP32-CAM
// ================================================
// I2C usa GPIO que NO entran en conflicto con cámara
#define I2C_SDA     12  // Disponible
#define I2C_SCL     13  // Disponible

// Sensor Ultrasónico FRONTAL
#define TRIG_F      14  // Disponible
#define ECHO_F      15  // Disponible

// Buzzer y LED RGB (via PCA9685 canales libres)
// Los controlaremos desde el PCA9685 para no usar pines del ESP32

// Sensor de Color TCS3200
// *** AJUSTADOS PARA ESP32-CAM COMPACTO AI-THINKER - SIN CONFLICTOS ***
#define TCS_S0      2   // Disponible
#define TCS_S1      4   // Disponible
#define TCS_S2      16  // Disponible
#define TCS_S3      17  // Disponible
#define TCS_OUT     33  // Disponible

#define CAMERA_MODEL_AI_THINKER
#include "camera_pins.h"

// ================================================
// OBJETOS PCA9685
// ================================================
WebServer server(80);
Adafruit_PWMServoDriver pwm = Adafruit_PWMServoDriver();

// Canales PCA9685
#define M1_PWM   0    // Motor 1 PWM
#define M1_IN1   1    // Motor 1 Dirección A
#define M1_IN2   2    // Motor 1 Dirección B
#define M2_PWM   3    // Motor 2 PWM
#define M2_IN1   4    // Motor 2 Dirección A
#define M2_IN2   5    // Motor 2 Dirección B
#define SERVO_CAM 6   // Servo de la cámara (canal 6 del PCA9685)
#define LED_R    7    // LED RGB - Rojo
#define LED_G    8    // LED RGB - Verde
#define LED_B    9    // LED RGB - Azul
#define BUZZER   10   // Buzzer 5V

// ================================================
// VARIABLES DE ESTADO
// ================================================
volatile long dist_frontal = 100;
volatile bool emergencia = false;
unsigned long t_ultrasonido = 0;
unsigned long t_tcs = 0;
unsigned long t_wifi = 0;
int servo_angulo = 90; // 90 = centro/frente
int color_detectado = 0; // 0=nada, 1=plastico, 2=carton, 3=metal

const unsigned long WIFI_RETRY_MS = 4000;
const unsigned long WIFI_CONNECT_TIMEOUT_MS = 3000;
int wifi_fail_count = 0;
bool wifi_use_static = true;

// ================================================
// FUNCIONES AUXILIARES
// ================================================

const char* wifi_status_str(wl_status_t st) {
    switch (st) {
        case WL_CONNECTED: return "CONECTADO";
        case WL_NO_SSID_AVAIL: return "SSID_NO_DISP";
        case WL_CONNECT_FAILED: return "FALLO_AUTH";
        case WL_CONNECTION_LOST: return "CONEXION_PERDIDA";
        case WL_DISCONNECTED: return "DESCONECTADO";
        case WL_IDLE_STATUS: return "OCIOSO";
        default: return "DESCONOCIDO";
    }
}

void iniciar_wifi(bool usar_static) {
    WiFi.disconnect(true, true);
    WiFi.mode(WIFI_STA);
    WiFi.setSleep(false);
    WiFi.setAutoReconnect(true);
    WiFi.persistent(false);
    WiFi.setTxPower(WIFI_POWER_19_5dBm);
    WiFi.setHostname("ARVE-ESP32");
    wifi_use_static = usar_static;

    if (usar_static && !WiFi.config(local_IP, gateway, subnet)) {
        Serial.println("[WARN] WiFi.config fallo, usando DHCP");
    }

    Serial.printf("Conectando a %s", ssid);
    WiFi.begin(ssid, password);
}

void conectar_wifi() {
    iniciar_wifi(true);
    unsigned long start = millis();
    while (WiFi.status() != WL_CONNECTED && millis() - start < WIFI_CONNECT_TIMEOUT_MS) {
        delay(200);
        Serial.print(".");
    }
    if (WiFi.status() == WL_CONNECTED) {
        wifi_fail_count = 0;
        Serial.printf("\n[OK] WiFi listo. IP: %s\n", WiFi.localIP().toString().c_str());
    } else {
        Serial.println("\n[WARN] WiFi no conectado aún, seguirá intentando en segundo plano.");
    }
}

void asegurar_wifi() {
    if (WiFi.status() == WL_CONNECTED) return;

    unsigned long ahora = millis();
    if (ahora - t_wifi < WIFI_RETRY_MS) return;
    t_wifi = ahora;

    wl_status_t st = WiFi.status();
    Serial.printf("[WARN] WiFi %s. Reintentando...\n", wifi_status_str(st));
    wifi_fail_count++;

    if (wifi_fail_count % 3 == 0) {
        iniciar_wifi(!wifi_use_static); // alterna entre IP fija y DHCP
        return;
    }

    WiFi.reconnect();
}

// Convertir ángulo a pulso PWM para el servo
int angulo_a_pwm(int angulo) {
    return map(angulo, 0, 180, 102, 512);
}

void setServo(int angulo) {
    servo_angulo = constrain(angulo, 0, 180);
    pwm.setPWM(SERVO_CAM, 0, angulo_a_pwm(servo_angulo));
}

void setLED(int r, int g, int b) {
    // PCA9685: 0=OFF, 4095=ON para canales LED (máximo válido)
    pwm.setPWM(LED_R, 0, r ? 4095 : 0);
    pwm.setPWM(LED_G, 0, g ? 4095 : 0);
    pwm.setPWM(LED_B, 0, b ? 4095 : 0);
}

void beep(int veces) {
    for (int i = 0; i < veces; i++) {
        pwm.setPWM(BUZZER, 0, 4095);    // ON (máximo válido)
        delay(100);
        pwm.setPWM(BUZZER, 0, 0);       // OFF
        delay(80);
    }
}

void setMotor(int m, int speed) {
    if (emergencia && speed > 0) speed = 0;
    int ch_pwm = (m == 1) ? M1_PWM : M2_PWM;
    int in1    = (m == 1) ? M1_IN1 : M2_IN1;
    int in2    = (m == 1) ? M1_IN2 : M2_IN2;
    speed = constrain(speed, -4095, 4095);
    if (speed > 0) {
        pwm.setPWM(in1, 4095, 0); pwm.setPWM(in2, 0, 4095);
        pwm.setPWM(ch_pwm, 0, speed);
    } else if (speed < 0) {
        pwm.setPWM(in1, 0, 4095); pwm.setPWM(in2, 4095, 0);
        pwm.setPWM(ch_pwm, 0, abs(speed));
    } else {
        pwm.setPWM(in1, 0, 4095); pwm.setPWM(in2, 0, 4095);
        pwm.setPWM(ch_pwm, 0, 0);
    }
}

long medir_distancia(int trig, int echo) {
    digitalWrite(trig, LOW); delayMicroseconds(2);
    digitalWrite(trig, HIGH); delayMicroseconds(10);
    digitalWrite(trig, LOW);
    long dur = pulseIn(echo, HIGH, 5000);
    return dur * 0.034 / 2;
}

// ================================================
// SENSOR DE COLOR TCS3200
// ================================================
long leer_frecuencia_color(int s2_val, int s3_val) {
    digitalWrite(TCS_S2, s2_val);
    digitalWrite(TCS_S3, s3_val);
    // Cambiado: quitamos delay(10) y bajamos el timeout de pulseIn de 50000 a 5000us para evitar congelar el ESP32
    return pulseIn(TCS_OUT, LOW, 5000);
}

int identificar_material() {
    long rojo    = leer_frecuencia_color(LOW, LOW);
    long verde   = leer_frecuencia_color(HIGH, HIGH);
    long azul    = leer_frecuencia_color(LOW, HIGH);
    
    // Clasificación por color dominante
    if (rojo < verde && rojo < azul)   return 1; // Rojo = Plástico/PET
    if (azul < rojo  && azul < verde)  return 2; // Azul = Vidrio/Plástico
    if (verde < rojo && verde < azul)  return 3; // Verde = Botella vidrio
    return 0; // Indefinido = Metal/Papel
}

// ================================================
// MJPEG STREAM
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
                delay(15); // Da tiempo a la pila WiFi para procesar
            }
            client.stop();
        }
        delay(50);
    }
}

// ================================================
// RUTAS HTTP
// ================================================
void handle_move() {
    setMotor(1, server.arg("v1").toInt());
    setMotor(2, server.arg("v2").toInt());
    server.send(200, "text/plain", "OK");
}

void handle_servo() {
    setServo(server.arg("ang").toInt());
    server.send(200, "text/plain", "OK");
}

void handle_beep() {
    beep(server.arg("n").toInt());
    server.send(200, "text/plain", "OK");
}

void handle_led() {
    setLED(server.arg("r").toInt(), server.arg("g").toInt(), server.arg("b").toInt());
    server.send(200, "text/plain", "OK");
}

void handle_status() {
    String json = "{";
    json += "\"dist_f\":" + String(dist_frontal) + ",";
    json += "\"emergencia\":" + String(emergencia ? "true" : "false") + ",";
    json += "\"servo\":" + String(servo_angulo) + ",";
    json += "\"material\":" + String(color_detectado);
    json += "}";
    server.send(200, "application/json", json);
}

// ================================================
// SETUP
// ================================================
void setup() {
    setCpuFrequencyMhz(240);
    Serial.begin(115200);
    iniciar_wifi(true);
    
    // Pines sensores
    pinMode(TRIG_F, OUTPUT); pinMode(ECHO_F, INPUT);
    pinMode(TCS_S0, OUTPUT); pinMode(TCS_S1, OUTPUT);
    pinMode(TCS_S2, OUTPUT); pinMode(TCS_S3, OUTPUT);
    pinMode(TCS_OUT, INPUT);
    
    // TCS3200: Escala al 20%
    digitalWrite(TCS_S0, HIGH); digitalWrite(TCS_S1, LOW);

    Wire.begin(I2C_SDA, I2C_SCL);
    pwm.begin();
    pwm.setPWMFreq(50); // 50Hz para servos

    // Posición inicial del servo (centro)
    setServo(90);
    setLED(0, 0, 1); // Azul = Iniciando
    beep(1);

    // Cámara
    bool has_psram = psramFound();
    camera_config_t config;
    config.ledc_channel = LEDC_CHANNEL_0; config.ledc_timer = LEDC_TIMER_0;
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
    config.grab_mode = CAMERA_GRAB_LATEST;
    if (has_psram) {
        config.frame_size = FRAMESIZE_QVGA; // Cambiado a QVGA (320x240) para máxima estabilidad, menos lag y alinearse con el input de YOLO (320x320)
        config.jpeg_quality = 12; // Aumentado a 12 para reducir tamaño de paquete y evitar corrupción por WiFi
        config.fb_count = 2;
        config.fb_location = CAMERA_FB_IN_PSRAM;
    } else {
        config.frame_size = FRAMESIZE_QVGA;
        config.jpeg_quality = 14;
        config.fb_count = 1;
    }

    if (esp_camera_init(&config) != ESP_OK) {
        Serial.println("ERROR CAMARA");
        setLED(1, 0, 0); // Rojo = Error
        return;
    }

    sensor_t* s = esp_camera_sensor_get();
    s->set_brightness(s, 1);
    s->set_contrast(s, 1);
    s->set_gain_ctrl(s, 1);
    s->set_exposure_ctrl(s, 1);
    s->set_whitebal(s, 1);
    s->set_awb_gain(s, 1);

    conectar_wifi();

    xTaskCreatePinnedToCore(stream_task, "stream_task", 8192, NULL, 1, NULL, 0);
    server.on("/move",   handle_move);
    server.on("/servo",  handle_servo);
    server.on("/beep",   handle_beep);
    server.on("/led",    handle_led);
    server.on("/status", handle_status);
    server.begin();
    
    setLED(0, 1, 0); // Verde = Online
    beep(2);
    if (WiFi.status() == WL_CONNECTED) {
        Serial.printf("\nARVE ELITE v5.0 ONLINE - %s\n", WiFi.localIP().toString().c_str());
    } else {
        Serial.println("\nARVE ELITE v5.0 ONLINE - WiFi pendiente");
    }
}

// ================================================
// LOOP - No bloqueante
// ================================================
void loop() {
    server.handleClient();

    unsigned long ahora = millis();
    asegurar_wifi();

    // Ultrasonido frontal cada 100ms
    if (ahora - t_ultrasonido >= 100) {
        t_ultrasonido = ahora;
        dist_frontal = medir_distancia(TRIG_F, ECHO_F);
        
        if (dist_frontal > 0 && dist_frontal < 20) {
            if (!emergencia) {
                emergencia = true;
                setMotor(1, 0); setMotor(2, 0);
                setLED(1, 0, 0); // Rojo = Peligro
                beep(3);
                Serial.println("EMERGENCIA: OBSTACULO!");
            }
        } else {
            emergencia = false;
            setLED(0, 1, 0); // Verde = OK
        }
    }

    // Sensor de color cada 500ms
    if (ahora - t_tcs >= 500) {
        t_tcs = ahora;
        color_detectado = identificar_material();
    }
}
