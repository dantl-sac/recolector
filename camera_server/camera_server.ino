// ================================================
// ARVE ELITE - FIRMWARE ESP32-CAM v6.2 (WiFi)
// Componentes: ESP32-CAM AI Thinker, TB6612FNG,
// PCA9685, HC-SR04 x2, Servo SG90, LED RGB, Buzzer.
// ================================================
#include "esp_camera.h"
#include <WiFi.h>
#include <WebServer.h>
#include <Wire.h>
#include <Adafruit_PWMServoDriver.h>

// Modo ligero: solo camara + motores + servo (sin sensores)
#define LITE_MODE 0

// Perfil de sensores: 1 = ultrasonicos (frontal + trasero), 2 = TCS3200
#define SENSOR_PROFILE 1

#if SENSOR_PROFILE == 1
#define USE_REAR_ULTRASONIC 1
#define USE_TCS3200 0
#elif SENSOR_PROFILE == 2
#define USE_REAR_ULTRASONIC 0
#define USE_TCS3200 1
#else
#error "SENSOR_PROFILE invalido. Usa 1 (ultrasonicos) o 2 (TCS3200)."
#endif

#if LITE_MODE
#undef USE_REAR_ULTRASONIC
#undef USE_TCS3200
#define USE_REAR_ULTRASONIC 0
#define USE_TCS3200 0
#endif

#if USE_REAR_ULTRASONIC && USE_TCS3200
#error "El ESP32-CAM no puede usar 2 HC-SR04 y TCS3200 a la vez sin un expansor de pines."
#endif

// --- RED ---
const char* ssid = "ARVE-07";
const char* password = "12345678";
IPAddress local_IP(192, 168, 137, 100);
IPAddress gateway(192, 168, 137, 1);
IPAddress subnet(255, 255, 255, 0);

// ================================================
// PINES FISICOS DEL ESP32-CAM AI THINKER
// ================================================
// I2C para el PCA9685
#define I2C_SDA     13
#define I2C_SCL     12

// Ultrasonico frontal
#define TRIG_F      14
#define ECHO_F      15

// Ultrasonico trasero opcional
#if USE_REAR_ULTRASONIC
#define TRIG_R      16
#define ECHO_R      4
#endif

// TCS3200 opcional
#if USE_TCS3200
#define TCS_S0      2
#define TCS_S1      4
#define TCS_S2      16
#define TCS_S3      0
#define TCS_OUT     3
#endif

#define CAMERA_MODEL_AI_THINKER
#include "camera_pins.h"

// ================================================
// OBJETOS PCA9685
// ================================================
WebServer server(80);
Adafruit_PWMServoDriver pwm = Adafruit_PWMServoDriver();

// Canales PCA9685
#define M1_PWM   0    // Motor 1 PWM
#define M1_IN1   1    // Motor 1 Direccion A
#define M1_IN2   2    // Motor 1 Direccion B
#define M2_PWM   3    // Motor 2 PWM
#define M2_IN1   4    // Motor 2 Direccion A
#define M2_IN2   5    // Motor 2 Direccion B
#define SERVO_CAM 6   // Servo de la camara (canal 6 del PCA9685)
#define LED_R    7    // LED RGB - Rojo
#define LED_G    8    // LED RGB - Verde
#define LED_B    9    // LED RGB - Azul
#define BUZZER   10   // Buzzer 5V

// ================================================
// VARIABLES DE ESTADO
// ================================================
volatile long dist_frontal = 100;
volatile long dist_trasera = 100;
volatile bool emergencia = false;
unsigned long t_ultrasonido = 0;
unsigned long t_tcs = 0;
unsigned long t_wifi = 0;
int servo_angulo = 90; // 90 = centro/frente
int color_detectado = 0; // 0=nada, 1=plastico, 2=carton, 3=metal
bool modo_auto = false;
int velocidad_base = 1800;
int velocidad_giro = 1400;
int obstaculo_cm = 22;
unsigned long t_auto = 0;
float ai_x = 0.5f;
int ai_dist_cm = 0;
float ai_conf = 0.0f;
unsigned long t_ai_ms = 0;
const unsigned long AI_TIMEOUT_MS = 1200;
// Umbral minimo de confianza para que el ESP32 actue sobre la deteccion AI
const float AI_CONF_THRESHOLD = 0.60f;
String ai_class = "";
bool explore_forward = true;
unsigned long t_explore = 0;
const unsigned long EXPLORE_FWD_MS = 1800;
const unsigned long EXPLORE_TURN_MS = 650;

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
		Serial.println("\n[WARN] WiFi no conectado aun, seguira intentando en segundo plano.");
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

// Convertir angulo a pulso PWM para el servo
int angulo_a_pwm(int angulo) {
	return map(angulo, 0, 180, 102, 512);
}

void setServo(int angulo) {
	servo_angulo = constrain(angulo, 0, 180);
	pwm.setPWM(SERVO_CAM, 0, angulo_a_pwm(servo_angulo));
}

void setLED(int r, int g, int b) {
	// PCA9685: 0=OFF, 4095=ON para canales LED (maximo valido)
	pwm.setPWM(LED_R, 0, r ? 4095 : 0);
	pwm.setPWM(LED_G, 0, g ? 4095 : 0);
	pwm.setPWM(LED_B, 0, b ? 4095 : 0);
}

void beep(int veces) {
	for (int i = 0; i < veces; i++) {
		pwm.setPWM(BUZZER, 0, 4095);    // ON (maximo valido)
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
	unsigned long dur = pulseIn(echo, HIGH, 8000);
	if (dur == 0) return -1;
	return (long)(dur * 0.0343f / 2.0f);
}

// ================================================
// SENSOR DE COLOR TCS3200
// ================================================
#if USE_TCS3200
long leer_frecuencia_color(int s2_val, int s3_val) {
	digitalWrite(TCS_S2, s2_val);
	digitalWrite(TCS_S3, s3_val);
	return pulseIn(TCS_OUT, LOW, 5000);
}

int identificar_material() {
	long rojo    = leer_frecuencia_color(LOW, LOW);
	long verde   = leer_frecuencia_color(HIGH, HIGH);
	long azul    = leer_frecuencia_color(LOW, HIGH);

	if (rojo < verde && rojo < azul)   return 1; // Rojo = Plastico/PET
	if (azul < rojo  && azul < verde)  return 2; // Azul = Vidrio/Plastico
	if (verde < rojo && verde < azul)  return 3; // Verde = Botella vidrio
	return 0; // Indefinido = Metal/Papel
}
#else
int identificar_material() {
	return 0;
}
#endif

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
	json += "\"dist_f\":" + String(dist_frontal > 0 ? dist_frontal : 0) + ",";
	json += "\"dist_r\":" + String(dist_trasera > 0 ? dist_trasera : 0) + ",";
	json += "\"emergencia\":" + String(emergencia ? "true" : "false") + ",";
	json += "\"servo\":" + String(servo_angulo) + ",";
	json += "\"material\":" + String(color_detectado) + ",";
	json += "\"rear_ultrasonic\":" + String(USE_REAR_ULTRASONIC ? "true" : "false") + ",";
	json += "\"tcs_enabled\":" + String(USE_TCS3200 ? "true" : "false") + ",";
	json += "\"lite_mode\":" + String(LITE_MODE ? "true" : "false") + ",";
	json += "\"modo_auto\":" + String(modo_auto ? "true" : "false") + ",";
	json += "\"velocidad_base\":" + String(velocidad_base) + ",";
	json += "\"obstaculo_cm\":" + String(obstaculo_cm) + ",";
	json += "\"ai_x\":" + String(ai_x, 3) + ",";
	json += "\"ai_dist_cm\":" + String(ai_dist_cm) + ",";
	json += "\"ai_conf\":" + String(ai_conf, 3) + ",";
	json += "\"ai_age_ms\":" + String(millis() - t_ai_ms) + ",";
	json += "\"ai_class\":\"" + ai_class + "\"";
	json += "}";
	server.send(200, "application/json", json);
}

void handle_ai() {
	if (server.hasArg("x")) {
		ai_x = constrain(server.arg("x").toFloat(), 0.0f, 1.0f);
	}
	if (server.hasArg("dist")) {
		ai_dist_cm = constrain(server.arg("dist").toInt(), 0, 999);
	}
	if (server.hasArg("conf")) {
		ai_conf = constrain(server.arg("conf").toFloat(), 0.0f, 1.0f);
	}
	if (server.hasArg("cls")) {
		ai_class = server.arg("cls");
	}
	t_ai_ms = millis();
	server.send(200, "text/plain", "OK");
}

void handle_mode() {
	String m = server.arg("m");
	m.toLowerCase();
	if (m == "auto") {
		modo_auto = true;
	} else if (m == "manual") {
		modo_auto = false;
		setMotor(1, 0);
		setMotor(2, 0);
	}
	server.send(200, "text/plain", "OK");
}

void handle_speed() {
	if (server.hasArg("base")) {
		velocidad_base = constrain(server.arg("base").toInt(), 500, 4095);
	}
	if (server.hasArg("turn")) {
		velocidad_giro = constrain(server.arg("turn").toInt(), 500, 4095);
	}
	server.send(200, "text/plain", "OK");
}

void handle_threshold() {
	if (server.hasArg("cm")) {
		obstaculo_cm = constrain(server.arg("cm").toInt(), 5, 200);
	}
	server.send(200, "text/plain", "OK");
}

void handle_root() {
	String html = "<!doctype html><html><head><meta charset='utf-8'>";
	html += "<meta name='viewport' content='width=device-width,initial-scale=1'>";
	html += "<title>ARVE Control</title>";
	html += "<style>body{font-family:Arial;margin:16px;background:#101418;color:#e6e6e6;}";
	html += ".grid{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;max-width:360px;}";
	html += "button{padding:12px;border:0;border-radius:8px;background:#2b3038;color:#fff;font-size:16px;}";
	html += "button:active{background:#3a414c;} .row{margin:12px 0;}";
	html += "input{width:100%;} a{color:#6ab0ff;}";
	html += "</style></head><body>";
	html += "<h2>ARVE Control WiFi</h2>";
	html += "<div class='row grid'>";
	html += "<button onclick=move(0,0)>STOP</button>";
	html += "<button onclick=move(base,base)>AVANZAR</button>";
	html += "<button onclick=move(-base,-base)>ATRAS</button>";
	html += "<button onclick=move(-turn,turn)>IZQ</button>";
	html += "<button onclick=move(turn,-turn)>DER</button>";
	html += "<button onclick=beep(2)>BEEP</button>";
	html += "</div>";
	html += "<div class='row'>";
	html += "<label>Servo <span id='servoVal'>90</span></label>";
	html += "<input type='range' min='0' max='180' value='90' oninput='setServo(this.value)'>";
	html += "</div>";
	html += "<div class='row'>";
	html += "</div>";
	html += "<div class='row'>";
	html += "</div>";
	html += "<div class='row grid'>";
	html += "<button onclick=setLed(1,0,0)>LED R</button>";
	html += "<button onclick=setLed(0,1,0)>LED G</button>";
	html += "<button onclick=setLed(0,0,1)>LED B</button>";
	html += "<button onclick=setMode(""manual"")>MANUAL</button>";
	html += "<button onclick=setMode(""auto"")>AUTO</button>";
	html += "<a href='http://" + WiFi.localIP().toString() + ":81' target='_blank'>Stream</a>";
	html += "</div>";
	html += "<pre id='status'></pre>";
	html += "<label>Velocidad base <span id='baseVal'>1800</span></label>";
	html += "<input type='range' min='500' max='4095' value='1800' oninput='setBase(this.value)'>";
	html += "<label>Obstaculo (cm) <span id='obsVal'>22</span></label>";
	html += "<input type='range' min='5' max='200' value='22' oninput='setObs(this.value)'>";
	html += "<script>";
	html += "let base=1800,turn=1400;";
	html += "function api(p){fetch(p).catch(()=>{});}";
	html += "function move(v1,v2){api('/move?v1='+v1+'&v2='+v2);}";
	html += "function setServo(a){document.getElementById('servoVal').textContent=a;api('/servo?ang='+a);}";
	html += "function setLed(r,g,b){api('/led?r='+r+'&g='+g+'&b='+b);}";
	html += "function beep(n){api('/beep?n='+n);}";
	html += "function setMode(m){api('/mode?m='+m);}";
	html += "function setBase(v){base=parseInt(v);document.getElementById('baseVal').textContent=v;api('/speed?base='+v+'&turn='+turn);}";
	html += "function setObs(v){document.getElementById('obsVal').textContent=v;api('/threshold?cm='+v);}";
	html += "setInterval(()=>fetch('/status').then(r=>r.json()).then(j=>{document.getElementById('status').textContent=JSON.stringify(j,null,2);}).catch(()=>{}),1000);";
	html += "</script></body></html>";
	server.send(200, "text/html", html);
}

// ================================================
// SETUP
// ================================================
void setup() {
	setCpuFrequencyMhz(240);
	Serial.begin(115200);
	iniciar_wifi(true);

#if !LITE_MODE
	// Pines sensores
	pinMode(TRIG_F, OUTPUT); pinMode(ECHO_F, INPUT);
#if USE_REAR_ULTRASONIC
	pinMode(TRIG_R, OUTPUT); pinMode(ECHO_R, INPUT);
#endif
#if USE_TCS3200
	pinMode(TCS_S0, OUTPUT); pinMode(TCS_S1, OUTPUT);
	pinMode(TCS_S2, OUTPUT); pinMode(TCS_S3, OUTPUT);
	pinMode(TCS_OUT, INPUT);

	// TCS3200: Escala al 20%
	digitalWrite(TCS_S0, HIGH); digitalWrite(TCS_S1, LOW);
#endif
#endif

	Wire.begin(I2C_SDA, I2C_SCL);
	pwm.begin();
	pwm.setPWMFreq(50); // 50Hz para servos

	// Posicion inicial del servo (centro)
	setServo(90);
	setLED(0, 0, 1); // Azul = Iniciando
	beep(1);

	// Camara
	bool has_psram = psramFound();
	camera_config_t config = {};
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
	server.on("/mode",   handle_mode);
	server.on("/speed",  handle_speed);
	server.on("/threshold", handle_threshold);
	server.on("/ai", handle_ai);
	server.on("/", handle_root);
	server.begin();

	setLED(0, 1, 0); // Verde = Online
	beep(2);
	if (WiFi.status() == WL_CONNECTED) {
		Serial.printf("\nARVE ELITE v6.2 ONLINE - %s\n", WiFi.localIP().toString().c_str());
	} else {
		Serial.println("\nARVE ELITE v6.2 ONLINE - WiFi pendiente");
	}
}

// ================================================
// LOOP - No bloqueante
// ================================================
void loop() {
	server.handleClient();

	unsigned long ahora = millis();
	asegurar_wifi();

#if !LITE_MODE
	// Ultrasonido frontal cada 100ms
	if (ahora - t_ultrasonido >= 100) {
		t_ultrasonido = ahora;
		dist_frontal = medir_distancia(TRIG_F, ECHO_F);
#if USE_REAR_ULTRASONIC
		dist_trasera = medir_distancia(TRIG_R, ECHO_R);
#endif

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
#if USE_TCS3200
	if (ahora - t_tcs >= 500) {
		t_tcs = ahora;
		color_detectado = identificar_material();
	}
#endif

	if (modo_auto && (ahora - t_auto >= 150)) {
		t_auto = ahora;
		bool obstaculo = (dist_frontal > 0 && dist_frontal < obstaculo_cm);
		bool ai_activa = (millis() - t_ai_ms) < AI_TIMEOUT_MS && ai_conf >= AI_CONF_THRESHOLD;

		if (obstaculo) {
			setMotor(1, -velocidad_giro);
			setMotor(2, velocidad_giro);
		} else if (ai_activa) {
			int base = velocidad_base;
			if (ai_dist_cm > 0 && ai_dist_cm < 30) {
				base = max(800, velocidad_base / 2);
			}
			if (ai_x < 0.45f) {
				setMotor(1, base - velocidad_giro);
				setMotor(2, base + velocidad_giro);
			} else if (ai_x > 0.55f) {
				setMotor(1, base + velocidad_giro);
				setMotor(2, base - velocidad_giro);
			} else {
				setMotor(1, base);
				setMotor(2, base);
			}
		} else {
			if (ahora - t_explore >= (explore_forward ? EXPLORE_FWD_MS : EXPLORE_TURN_MS)) {
				explore_forward = !explore_forward;
				t_explore = ahora;
			}
			if (explore_forward) {
				setMotor(1, velocidad_base);
				setMotor(2, velocidad_base);
			} else {
				setMotor(1, -velocidad_giro);
				setMotor(2, velocidad_giro);
			}
		}
	}
#endif
}
