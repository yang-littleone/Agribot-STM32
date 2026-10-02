#ifndef AGRIBOT_BLUETOOTH_H
#define AGRIBOT_BLUETOOTH_H
#include <stdint.h>
void Bluetooth_Bootstrap(void);
uint32_t Bluetooth_DetectedBaud(void);
uint8_t Bluetooth_ATVerified(void);
const char *Bluetooth_LastReplyHex(void);
#endif
