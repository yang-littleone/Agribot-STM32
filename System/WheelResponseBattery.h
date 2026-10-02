#ifndef WHEEL_RESPONSE_BATTERY_H
#define WHEEL_RESPONSE_BATTERY_H
#include <stdint.h>
#define WRS_BATTERY_INVALID 65535u
/* Nominal estimate: original PB0 ADC1_IN8, 3.3 V reference and x11 divider.
 * UART task alone calls Poll; the control task only reads the cached estimate. */
void WRS_BatteryPoll(uint32_t now_ms);
uint16_t WRS_BatteryMv(uint32_t now_ms);
uint16_t WRS_BatteryRaw(void);
#endif
