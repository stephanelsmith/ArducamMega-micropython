#define MICROPY_HW_BOARD_NAME "FeatherS2"
#define MICROPY_HW_MCU_NAME "ESP32-S2"
#define MICROPY_PY_NETWORK_HOSTNAME_DEFAULT "FeatherS2"

#define MICROPY_PY_BLUETOOTH                (0)
#define MICROPY_HW_ENABLE_SDCARD            (0)

#define MICROPY_HW_I2C0_SCL (9)
#define MICROPY_HW_I2C0_SDA (8)

//spi1
#define MICROPY_HW_SPI1_MOSI (35)  // SDO
#define MICROPY_HW_SPI1_MISO (37)  // SDI
#define MICROPY_HW_SPI1_SCK (36)

//spi2
#define MICROPY_HW_SPI2_MOSI (16)  // SDO
#define MICROPY_HW_SPI2_MISO (18)  // SDI
#define MICROPY_HW_SPI2_SCK (17)


#define MICROPY_HW_UART_REPL_BAUD  921600

// turn-off unused
// https://github.com/orgs/micropython/discussions/14473
#define MICROPY_HW_ENABLE_SDCARD            (0)
#define MICROPY_PY_MACHINE_DAC              (0)
#define MICROPY_PY_ESPNOW                   (0)
#define MICROPY_PY_NETWORK_LAN              (0)
#define MICROPY_PY_WEBREPL                  (0)
#define MICROPY_ENABLE_COMPILER (1)

// enable encryption
#define MICROPY_PY_SSL (1)
#define MICROPY_SSL_MBEDTLS (1)
#define MICROPY_PY_CRYPTOLIB (1)
#define MICROPY_PY_HASHLIB (1)

