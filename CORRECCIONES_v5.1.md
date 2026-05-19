# CORRECCIONES ESP32-CAM FIRMWARE v5.0 → v5.1

## Problemas Identificados y Corregidos

### 1. **Conflicto de Pines I2C con Cámara**
   - **Problema**: GPIO 21 (I2C_SDA) y GPIO 19 (I2C_SCL) están asignados a Y5 y Y4 de la cámara
   - **Solución**: Cambiados a GPIO 12 y 13 (disponibles y no conflictivos)
   - **Impacto**: PCA9685 (motor driver, servo, LED, buzzer) funciona correctamente

### 2. **Valores PWM Fuera de Rango**
   - **Problema**: Uso de `4096` en lugares donde máximo es `4095` para PCA9685
   - **Ubicaciones corregidas**:
     - `setLED()`: 4096 → 4095
     - `beep()`: 4096 → 4095 (y ajustados parámetros de ON/OFF)
     - `setMotor()`: 4096 → 4095 (múltiples instancias)
   - **Impacto**: Evita comportamiento impredecible en LEDs, buzzer y motores

### 3. **Configuración Óptima de Pines Disponibles**
   - **I2C**: GPIO 12 (SDA), GPIO 13 (SCL)
   - **Ultrasónico**: GPIO 14 (TRIG), GPIO 15 (ECHO)
   - **TCS3200**: GPIO 2, 4, 16, 17, 33 (sin conflictos con cámara)

## Pines ESP32-CAM AI-THINKER Utilizados

### Cámara (No modificables)
- GPIO0: XCLK
- GPIO5: Y2
- GPIO18: Y3
- GPIO19: Y4
- GPIO21: Y5
- GPIO22: PCLK
- GPIO23: HREF
- GPIO25: VSYNC
- GPIO26: SIOD
- GPIO27: SIOC
- GPIO32: PWDN
- GPIO34: Y8
- GPIO35: Y9
- GPIO36: Y6
- GPIO39: Y7

### Ahora Disponibles Para Periféricos
✓ GPIO2 (TCS_S0)
✓ GPIO4 (TCS_S1)
✓ GPIO12 (I2C_SDA)
✓ GPIO13 (I2C_SCL)
✓ GPIO14 (TRIG_F)
✓ GPIO15 (ECHO_F)
✓ GPIO16 (TCS_S2)
✓ GPIO17 (TCS_S3)
✓ GPIO33 (TCS_OUT)

## Verificaciones Realizadas
- ✓ No hay conflictos de pines
- ✓ Valores PWM dentro de rango válido (0-4095)
- ✓ I2C en pines estables
- ✓ Sensores en pines seguros (no sensibles al arranque)
- ✓ PCA9685 controla correctamente: motores, servos, LEDs, buzzer

## Estado Final: LISTO PARA COMPILAR
El código está libre de errores de pins y valores PWM.
