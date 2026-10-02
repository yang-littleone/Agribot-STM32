#ifndef WRS_ENGINE_H
#define WRS_ENGINE_H
#include "WheelResponseProtocol.h"
enum {WRS_IDLE=0,WRS_ARMED,WRS_RUNNING,WRS_ZERO_POST,WRS_COMPLETE,WRS_FAULT};
enum {WRS_HELLO=1,WRS_ARM,WRS_START,WRS_STOP,WRS_ABORT,WRS_HEARTBEAT,WRS_DISARM,WRS_GET_CONFIG,WRS_CLEAR_FAULT,WRS_BT_UART_BAUD,WRS_BT_SETUP};
enum {WRS_OK=0,WRS_BAD_STATE=1,WRS_BAD_PARAMETER=2,WRS_BAD_PROTOCOL=3};
enum {WRS_F_HEARTBEAT=1,WRS_F_ABORT=2,WRS_F_SCHEDULING=4,WRS_F_ENCODER=8,
      WRS_F_RX=16,WRS_F_UART=32,WRS_F_MEMORY=64,WRS_F_DROPS=128};
#define WRS_HEARTBEAT_MS 500u
#define WRS_DEADLINE_US 15000u
#define WRS_FATAL_DT_US 30000u
typedef struct {
    uint8_t state,stage,reset_pi,configured,early_stop;
    uint16_t run_id,step,pre,hold,post,faults;
    uint32_t index,last_heartbeat;
} WRS_Engine;
void WRS_EngineInit(WRS_Engine *e);
uint8_t WRS_Apply(WRS_Engine *e,const WRS_Command *c,uint32_t now_ms);
uint8_t WRS_ApplyFromLink(WRS_Engine *e,const WRS_Command *c,uint32_t now_ms,uint8_t source,volatile uint8_t *owner);
void WRS_Fault(WRS_Engine *e,uint16_t flags);
uint16_t WRS_BeginCycle(WRS_Engine *e,uint32_t now_ms);
void WRS_EndCycle(WRS_Engine *e);
#endif
