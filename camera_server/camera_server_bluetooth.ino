// ================================================
// ARVE ELITE - FIRMWARE CON BLUETOOTH v5.2
// Comunicación estable via BLE (Bluetooth Low Energy)
// ================================================
#include "esp_camera.h"
#include <BluetoothSerial.h>
#include <Wire.h>
#include <Adafruit_PWMServoDriver.h>

// ================================================
// BLUETOOTH
// ================================================
BluetoothSerial SerialBT;
const char* DEVICE_NAME = "ARVE-ELITE-v6.0";
const char* PIN_CODE = "1234";

// ================================================
// PINES FÍSICOS DEL ESP32-CAM
// ================================================
#define I2C_SDA     12  // Para PCA9685
#define I2C_SCL     13

// Sensor Ultrasónico FRONTAL
#define TRIG_F      14
#define ECHO_F      15

// Sensor de Color TCS3200
#define TCS_S0      2
#define TCS_S1      4
#define TCS_S2      16
#define TCS_S3      17
#define TCS_OUT     33

#define CAMERA_MODEL_AI_THINKER
#include "camera_pins.h"

// ================================================
// PCA9685 DRIVER
// ================================================
WebServer server(80);
Adafruit_PWMServoDriver pwm = Adafruit_PWMServoDriver();

#define M1_PWM   0    // Motor 1 PWM
#define M1_IN1   1    // Motor 1 Dirección A
#define M1_IN2   2    // Motor 1 Dirección B
#define M2_PWM   3    // Motor 2 PWM
#define M2_IN1   4    // Motor 2 Dirección A
#define M2_IN2   5    // Motor 2 Dirección B
#define SERVO_CAM 6   // Servo de la cámara
#define LED_R    7    // LED RGB - Rojo
#define LED_G    8    // LED RGB - Verde
#define LED_B    9    // LED RGB - Azul
#define BUZZER   10   // Buzzer 5V

// ================================================
// ESTADO DEL SISTEMA
// ================================================
volatile long dist_frontal = 100;
volatile bool emergencia = false;
unsigned long t_ultrasonido = 0;
unsigned long t_tcs = 0;
unsigned long t_sensor_report = 0;
int servo_angulo = 90;
int color_detectado = 0;

// Modo de operación
enum ModoOperacion {
    MODO_MANUAL,      // Control por BT manual
    MODO_AUTONOMO,    // Detección automática
    MODO_VISION,      // Enviar video por BT
};
ModoOperacion modo_actual = MODO_MANUAL;

// Buffer de envío
char buffer_tx[256];

// ================================================
// FUNCIONES BLUETOOTH
// ================================================
void enviarBT(const char* mensaje) {
    """Envía mensaje por Bluetooth con validación"""
    if (SerialBT.hasClient()) {
        SerialBT.println(mensaje);
        Serial.println("[BT TX] " + String(mensaje));
    }
}

void enviarJSON(const char* json) {
    """Envía JSON por BT (formato estandar para respuestas)"""
    if (SerialBT.hasClient()) {
        SerialBT.write((uint8_t*)json, strlen(json));
        SerialBT.write('\n');
        Serial.println("[BT JSON] " + String(json));
    }
}

void procesarComandoBT(String comando) {
    """Procesa comandos recibidos por Bluetooth"""
    Serial.println("[BT RX] " + comando);
    comando.trim();
    comando.toUpperCase();
    
    // Comando: MOVE <motor> <velocidad>
    if (comando.startsWith("MOVE")) {
        int motor = comando.charAt(5) - '0';           // '1' o '2'
        int velocidad = comando.substring(7).toInt();  // -4095 a 4095
        setMotor(motor, velocidad);
        snprintf(buffer_tx, sizeof(buffer_tx), "{\"cmd\":\"move\",\"m\":%d,\"v\":%d}", motor, velocidad);
        enviarJSON(buffer_tx);
    }
    
    // Comando: SERVO <angulo>
    else if (comando.startsWith("SERVO")) {
        int angulo = comando.substring(6).toInt();
        setServo(angulo);
        snprintf(buffer_tx, sizeof(buffer_tx), "{\"cmd\":\"servo\",\"ang\":%d}", angulo);
        enviarJSON(buffer_tx);
    }
    
    // Comando: LED <r> <g> <b>
    else if (comando.startsWith("LED")) {
        int r = comando[4] - '0';
        int g = comando[6] - '0';
        int b = comando[8] - '0';
        setLED(r, g, b);
        snprintf(buffer_tx, sizeof(buffer_tx), "{\"cmd\":\"led\",\"r\":%d,\"g\":%d,\"b\":%d}", r, g, b);
        enviarJSON(buffer_tx);
    }
    
    // Comando: BEEP <veces>
    else if (comando.startsWith("BEEP")) {
        int veces = comando.substring(5).toInt();
        beep(veces);
        snprintf(buffer_tx, sizeof(buffer_tx), "{\"cmd\":\"beep\",\"n\":%d}", veces);
        enviarJSON(buffer_tx);
    }
    
    // Comando: STATUS
    else if (comando == "STATUS") {
        snprintf(buffer_tx, sizeof(buffer_tx),
            "{\"status\":\"ok\",\"dist\":%ld,\"servo\":%d,\"emerg\":%s,\"color\":%d}",
            dist_frontal, servo_angulo, emergencia ? "true" : "false", color_detectado);
        enviarJSON(buffer_tx);
    }
    
    // Comando: MODE <modo>
    else if (comando.startsWith("MODE")) {
        String modo_str = comando.substring(5);
        if (modo_str == "MANUAL") {
            modo_actual = MODO_MANUAL;
            enviarBT("[OK] Modo MANUAL");
        } else if (modo_str == "AUTO") {
            modo_actual = MODO_AUTONOMO;
            enviarBT("[OK] Modo AUTOMÁTICO");
        }
    }
    
    // Comando: HELP
    else if (comando == "HELP") {
        enviarBT("=== COMANDOS ARVE ELITE v6.0 ===");
        enviarBT("MOVE <motor> <vel>  - Motor (1-2), vel (-4095 a 4095)");
        enviarBT("SERVO <ang>         - Ángulo (0-180)");
        enviarBT("LED <r> <g> <b>     - RGB (0-1)");
        enviarBT("BEEP <n>            - Buzzer (n veces)");
        enviarBT("STATUS              - Estado del sistema");
        enviarBT("MODE <MANUAL|AUTO>  - Cambiar modo");
        enviarBT("HELP                - Este mensaje");
    }
    
    else {
        snprintf(buffer_tx, sizeof(buffer_tx), "{\"error\":\"comando_desconocido\",\"cmd\":\"%s\"}", comando.c_str());
        enviarJSON(buffer_tx);
    }
}

// ================================================
// FUNCIONES DE CONTROL
// ================================================
void setLED(int r, int g, int b) {
    pwm.setPWM(LED_R, 0, r ? 4095 : 0);
    pwm.setPWM(LED_G, 0, g ? 4095 : 0);
    pwm.setPWM(LED_B, 0, b ? 4095 : 0);
}

void beep(int veces) {
    for (int i = 0; i < veces; i++) {
        pwm.setPWM(BUZZER, 0, 4095);
        delay(100);
        pwm.setPWM(BUZZER, 0, 0);
        delay(80);
    }
}

void setServo(int angulo) {
    servo_angulo = constrain(angulo, 0, 180);
    int pwm_val = map(servo_angulo, 0, 180, 102, 512);
    pwm.setPWM(SERVO_CAM, 0, pwm_val);
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

// Sensor de color
long leer_frecuencia_color(int s2_val, int s3_val) {
    digitalWrite(TCS_S2, s2_val);
    digitalWrite(TCS_S3, s3_val);
    return pulseIn(TCS_OUT, LOW, 5000);
}

int identificar_material() {
    long rojo    = leer_frecuencia_color(LOW, LOW);
    long verde   = leer_frecuencia_color(HIGH, HIGH);
    long azul    = leer_frecuencia_color(LOW, HIGH);
    
    if (rojo < verde && rojo < azul)   return 1; // Rojo
    if (azul < rojo  && azul < verde)  return 2; // Azul
    if (verde < rojo && verde < azul)  return 3; // Verde
    return 0; // Indefinido
}

// ================================================
// STREAM MJPEG (Para video por WiFi secundario)
// ================================================
void stream_task(void *pvParameters) {
    static WiFiServer stream_server(81);
    stream_server.begin();
    
    while (1) {
        WiFiClient client = stream_server.available();
        if (client) {
            client.printf("HTTP/1.1 200 OK\r\nContent-Type: multipart/x-mixed-replace;boundary=frame\r\n\r\n");
            while (client.connected()) {
                camera_fb_t* fb = esp_camera_fb_get();
                if (fb) {
                    client.write("--frame\r\n", 9);
                    client.printf("Content-Type: image/jpeg\r\nContent-Length: %u\r\n\r\n", fb->len);
                    client.write(fb->buf, fb->len);
                    client.write("\r\n", 2);
                    esp_camera_fb_return(fb);
                    delay(15);
                }
            }
            client.stop();
        }
        delay(50);
    }
}

// ================================================
// SETUP
// ================================================
void setup() {
    setCpuFrequencyMhz(240);
    Serial.begin(115200);
    
    // Bluetooth
    SerialBT.begin(DEVICE_NAME);
    Serial.println("[OK] Bluetooth iniciado");
    enviarBT("=== ARVE ELITE v6.0 ===");
    enviarBT("BLUETOOTH CONECTADO");
    enviarBT("Escribe 'HELP' para ver comandos");
    
    // Pines
    pinMode(TRIG_F, OUTPUT); pinMode(ECHO_F, INPUT);
    pinMode(TCS_S0, OUTPUT); pinMode(TCS_S1, OUTPUT);
    pinMode(TCS_S2, OUTPUT); pinMode(TCS_S3, OUTPUT);
    pinMode(TCS_OUT, INPUT);
    
    digitalWrite(TCS_S0, HIGH); digitalWrite(TCS_S1, LOW);
    
    // I2C y PCA9685
    Wire.begin(I2C_SDA, I2C_SCL);
    pwm.begin();
    pwm.setPWMFreq(50);
    
    // Inicialización visual
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
        config.frame_size = FRAMESIZE_QVGA;
        config.jpeg_quality = 12;
        config.fb_count = 2;
        config.fb_location = CAMERA_FB_IN_PSRAM;
    } else {
        config.frame_size = FRAMESIZE_QVGA;
        config.jpeg_quality = 14;
        config.fb_count = 1;
    }
    
    if (esp_camera_init(&config) != ESP_OK) {
        Serial.println("ERROR CAMARA");
        setLED(1, 0, 0);
        enviarBT("[ERROR] Cámara no inicializada");
        return;
    }
    
    sensor_t* s = esp_camera_sensor_get();
    s->set_brightness(s, 1);
    s->set_contrast(s, 1);
    s->set_gain_ctrl(s, 1);
    s->set_exposure_ctrl(s, 1);
    s->set_whitebal(s, 1);
    s->set_awb_gain(s, 1);
    
    // Stream MJPEG en segundo plano
    xTaskCreatePinnedToCore(stream_task, "stream_task", 8192, NULL, 1, NULL, 0);
    
    setLED(0, 1, 0); // Verde = Listo
    beep(2);
    Serial.println("[OK] ARVE ELITE v6.0 LISTA");
    enviarBT("[✓] Sistema listo para usar");
}

// ================================================
// LOOP PRINCIPAL
// ================================================
void loop() {
    // Procesar comandos BT
    if (SerialBT.available()) {
        String comando = SerialBT.readStringUntil('\n');
        procesarComandoBT(comando);
    }
    
    unsigned long ahora = millis();
    
    // Ultrasonido cada 100ms
    if (ahora - t_ultrasonido >= 100) {
        t_ultrasonido = ahora;
        dist_frontal = medir_distancia(TRIG_F, ECHO_F);
        
        if (dist_frontal > 0 && dist_frontal < 20) {
            if (!emergencia) {
                emergencia = true;
                setMotor(1, 0); setMotor(2, 0);
                setLED(1, 0, 0);
                beep(3);
                enviarBT("[⚠] EMERGENCIA: OBSTÁCULO DETECTADO");
            }
        } else {
            emergencia = false;
            setLED(0, 1, 0);
        }
    }
    
    // Sensor de color cada 500ms
    if (ahora - t_tcs >= 500) {
        t_tcs = ahora;
        color_detectado = identificar_material();
    }
    
    // Enviar telemetría cada 1 segundo
    if (ahora - t_sensor_report >= 1000) {
        t_sensor_report = ahora;
        snprintf(buffer_tx, sizeof(buffer_tx),
            "{\"telemetria\":{\"dist\":%ld,\"servo\":%d,\"color\":%d,\"modo\":%d}}",
            dist_frontal, servo_angulo, color_detectado, (int)modo_actual);
        enviarJSON(buffer_tx);
    }
    
    delay(10);
}
