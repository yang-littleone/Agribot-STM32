#include "WheelResponseEngine.h"
#include <string.h>
void WRS_EngineInit(WRS_Engine *e){memset(e,0,sizeof(*e));e->stage=255;e->reset_pi=1;}
/* USB=0, Bluetooth SPP=1. A valid HELLO may claim only a stopped session.
 * Non-owner heartbeats cannot prolong a moving session. ABORT works from either link.
 */
uint8_t WRS_ApplyFromLink(WRS_Engine *e,const WRS_Command *c,uint32_t now,uint8_t source,volatile uint8_t *owner){
    uint8_t status;
    if(source>1)return WRS_BAD_PROTOCOL;
    if(source!=*owner&&c->opcode!=WRS_HELLO&&c->opcode!=WRS_GET_CONFIG&&c->opcode!=WRS_ABORT)return WRS_BAD_STATE;
    status=WRS_Apply(e,c,now);
    if(status==WRS_OK&&c->opcode==WRS_HELLO&&(e->state==WRS_IDLE||e->state==WRS_COMPLETE||e->state==WRS_FAULT))*owner=source;
    return status;
}
void WRS_Fault(WRS_Engine *e,uint16_t flags){e->faults|=flags;e->state=WRS_FAULT;e->stage=255;e->reset_pi=1;}
static int plan_ok(const WRS_Command *c){
    return c->run_id&& (c->step==50||c->step==100||c->step==180||c->step==400)&&
        c->pre_ms&&c->hold_ms&&c->post_ms&&!(c->pre_ms%10)&&!(c->hold_ms%10)&&!(c->post_ms%10)&&
        (uint32_t)c->pre_ms+c->hold_ms+c->post_ms<=60000;
}
static int identical(const WRS_Engine *e,const WRS_Command *c){return e->run_id==c->run_id&&e->step==c->step&&
    e->pre*10u==c->pre_ms&&e->hold*10u==c->hold_ms&&e->post*10u==c->post_ms;}
uint8_t WRS_Apply(WRS_Engine *e,const WRS_Command *c,uint32_t now){
    if(c->reserved)return WRS_BAD_PROTOCOL;
    if(c->opcode==WRS_ARM){
        if(!plan_ok(c))return WRS_BAD_PARAMETER;
        if(e->state==WRS_ARMED&&identical(e,c))return WRS_OK;
        if(e->state!=WRS_IDLE&&e->state!=WRS_COMPLETE)return WRS_BAD_STATE;
        if(e->configured&&e->run_id==c->run_id)return WRS_BAD_PARAMETER;
        e->run_id=c->run_id;e->step=c->step;e->pre=c->pre_ms/10;e->hold=c->hold_ms/10;e->post=c->post_ms/10;
        e->state=WRS_ARMED;e->stage=255;e->index=0;e->last_heartbeat=now;e->reset_pi=1;e->configured=1;e->early_stop=0;
        return WRS_OK;
    }
    if(c->step||c->pre_ms||c->hold_ms||c->post_ms)return WRS_BAD_PARAMETER;
    switch(c->opcode){
    case WRS_HELLO:return WRS_OK;
    case WRS_GET_CONFIG:return (e->state==WRS_IDLE||e->state==WRS_COMPLETE||e->state==WRS_FAULT)?WRS_OK:WRS_BAD_STATE;
    case WRS_START:
        if(c->run_id!=e->run_id||!e->configured)return WRS_BAD_PARAMETER;
        if(e->state==WRS_RUNNING||e->state==WRS_ZERO_POST||e->state==WRS_COMPLETE)return WRS_OK;
        if(e->state!=WRS_ARMED)return WRS_BAD_STATE;
        if((uint32_t)(now-e->last_heartbeat)>WRS_HEARTBEAT_MS){WRS_Fault(e,WRS_F_HEARTBEAT);return WRS_BAD_STATE;}
        e->state=WRS_RUNNING;e->stage=0;e->index=0;return WRS_OK;
    case WRS_STOP:
        if(c->run_id!=e->run_id)return WRS_BAD_PARAMETER;
        if(e->state==WRS_ZERO_POST)return WRS_OK;
        if(e->state!=WRS_RUNNING)return WRS_BAD_STATE;
        e->state=WRS_ZERO_POST;e->stage=2;e->index=e->pre+e->hold;e->early_stop=1;return WRS_OK;
    case WRS_ABORT:WRS_Fault(e,WRS_F_ABORT);return WRS_OK;
    case WRS_HEARTBEAT:
        if(c->run_id!=e->run_id)return WRS_BAD_PARAMETER;
        if(e->state!=WRS_ARMED&&e->state!=WRS_RUNNING&&e->state!=WRS_ZERO_POST)return WRS_BAD_STATE;
        e->last_heartbeat=now;return WRS_OK;
    case WRS_DISARM:
        if(e->state!=WRS_ARMED&&e->state!=WRS_IDLE&&e->state!=WRS_COMPLETE)return WRS_BAD_STATE;
        e->state=WRS_IDLE;e->stage=255;e->reset_pi=1;return WRS_OK;
    case WRS_CLEAR_FAULT:
        if(e->state!=WRS_FAULT)return WRS_BAD_STATE;
        e->faults=0;e->state=WRS_IDLE;e->stage=255;e->reset_pi=1;return WRS_OK;
    default:return WRS_BAD_PROTOCOL;
    }
}
uint16_t WRS_BeginCycle(WRS_Engine *e,uint32_t now){
    if(e->state==WRS_ARMED||e->state==WRS_RUNNING||e->state==WRS_ZERO_POST)
        if((uint32_t)(now-e->last_heartbeat)>WRS_HEARTBEAT_MS)WRS_Fault(e,WRS_F_HEARTBEAT);
    if(e->state!=WRS_RUNNING&&e->state!=WRS_ZERO_POST){e->stage=255;return 0;}
    if(e->index<e->pre)e->stage=0;
    else if(e->index<(uint32_t)e->pre+e->hold)e->stage=1;
    else {e->stage=2;e->state=WRS_ZERO_POST;}
    return e->stage==1?e->step:0;
}
void WRS_EndCycle(WRS_Engine *e){
    if(e->state==WRS_RUNNING||e->state==WRS_ZERO_POST){
        e->index++;
        if(e->index>=(uint32_t)e->pre+e->hold+e->post){e->state=WRS_COMPLETE;e->stage=255;e->reset_pi=1;}
    }
}
