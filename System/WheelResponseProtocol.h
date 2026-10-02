#ifndef WRS_PROTOCOL_H
#define WRS_PROTOCOL_H
#include <stdint.h>
#include <stddef.h>
#define WRS_VERSION 1
#define WRS_TELEMETRY 1
#define WRS_COMMAND 16
#define WRS_ACK 17
#define WRS_CONFIG 18
#define WRS_SAMPLE_SIZE 84
typedef struct {
    uint32_t sequence, time_us, dt_us;
    uint16_t run_id;
    uint8_t state, stage;
    float v, w, target[4], feedback[4];
    int16_t pwm[4], encoder[4];
    uint16_t battery_mv, faults;
    uint32_t drops;
    uint16_t misses, exec_us;
} WRS_Sample;
typedef struct {
    uint32_t sequence;
    uint8_t opcode, reserved;
    uint16_t run_id, step, pre_ms, hold_ms, post_ms;
} WRS_Command;
typedef struct { uint8_t bytes[26]; uint16_t used; uint32_t errors; } WRS_Parser;
uint16_t WRS_CRC(const uint8_t *p, size_t n);
void WRS_Put16(uint8_t *p, uint16_t v);
void WRS_Put32(uint8_t *p, uint32_t v);
uint16_t WRS_Get16(const uint8_t *p);
uint32_t WRS_Get32(const uint8_t *p);
uint16_t WRS_Frame(uint8_t *out, uint8_t type, const uint8_t *payload, uint16_t n);
void WRS_EncodeSample(uint8_t *out, const WRS_Sample *s);
int WRS_ParseByte(WRS_Parser *p, uint8_t b, WRS_Command *cmd);
#endif
