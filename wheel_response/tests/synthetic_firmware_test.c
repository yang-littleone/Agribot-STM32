/* Host-only synthetic tests. Never used as measured vehicle data. */
#include "WheelResponseEngine.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
static void test_link_ownership(void){
    WRS_Engine e;uint8_t owner=0;WRS_Command c={1,WRS_HELLO,0,31,0,0,0,0};
    WRS_EngineInit(&e);
    c.reserved=1;assert(WRS_ApplyFromLink(&e,&c,0,1,&owner)==WRS_BAD_PROTOCOL&&owner==0);c.reserved=0;
    assert(WRS_ApplyFromLink(&e,&c,0,1,&owner)==WRS_OK&&owner==1&&e.state==WRS_IDLE);
    c.opcode=WRS_ARM;c.step=50;c.pre_ms=c.hold_ms=c.post_ms=1000;
    assert(WRS_ApplyFromLink(&e,&c,10,1,&owner)==WRS_OK);
    assert(WRS_ApplyFromLink(&e,&c,10,0,&owner)==WRS_BAD_STATE);
    c.opcode=WRS_HELLO;c.step=c.pre_ms=c.hold_ms=c.post_ms=0;
    assert(WRS_ApplyFromLink(&e,&c,20,0,&owner)==WRS_OK&&owner==1);
    c.opcode=WRS_HEARTBEAT;assert(WRS_ApplyFromLink(&e,&c,100,0,&owner)==WRS_BAD_STATE&&e.last_heartbeat==10);
    assert(WRS_ApplyFromLink(&e,&c,100,1,&owner)==WRS_OK&&e.last_heartbeat==100);
    c.opcode=WRS_START;assert(WRS_ApplyFromLink(&e,&c,100,1,&owner)==WRS_OK);
    c.opcode=WRS_STOP;assert(WRS_ApplyFromLink(&e,&c,110,0,&owner)==WRS_BAD_STATE&&e.state==WRS_RUNNING);
    c.opcode=WRS_HEARTBEAT;assert(WRS_ApplyFromLink(&e,&c,600,0,&owner)==WRS_BAD_STATE);
    WRS_BeginCycle(&e,601);assert(e.state==WRS_FAULT&&(e.faults&WRS_F_HEARTBEAT));
    c.opcode=WRS_ABORT;assert(WRS_ApplyFromLink(&e,&c,602,0,&owner)==WRS_OK&&(e.faults&WRS_F_ABORT));
    c.opcode=WRS_CLEAR_FAULT;assert(WRS_ApplyFromLink(&e,&c,603,0,&owner)==WRS_BAD_STATE);
    c.opcode=WRS_HELLO;assert(WRS_ApplyFromLink(&e,&c,604,0,&owner)==WRS_OK&&owner==0);
    c.opcode=WRS_CLEAR_FAULT;assert(WRS_ApplyFromLink(&e,&c,605,0,&owner)==WRS_OK&&e.state==WRS_IDLE);
}
int main(void){
    WRS_Engine e;WRS_Command c={1,WRS_ARM,0,7,180,3000,5000,3000},parsed;
    WRS_Parser parser={0};WRS_Sample s;uint8_t payload[84],packet[94];unsigned i,count[3]={0};
    test_link_ownership();
    assert(WRS_CRC((const uint8_t *)"123456789",9)==0x29b1);
    WRS_EngineInit(&e);assert(e.state==WRS_IDLE&&e.reset_pi);
    c.opcode=WRS_START;assert(WRS_Apply(&e,&c,0)!=WRS_OK);c.opcode=WRS_ARM;
    c.step=401;assert(WRS_Apply(&e,&c,0)==WRS_BAD_PARAMETER);c.step=180;
    c.pre_ms=3001;assert(WRS_Apply(&e,&c,0)==WRS_BAD_PARAMETER);c.pre_ms=3000;
    assert(WRS_Apply(&e,&c,0)==WRS_OK);assert(e.state==WRS_ARMED);assert(WRS_BeginCycle(&e,0)==0);
    c.opcode=WRS_START;c.step=c.pre_ms=c.hold_ms=c.post_ms=0;
    assert(WRS_Apply(&e,&c,0)==WRS_OK);e.reset_pi=0;
    for(i=0;i<1100;i++){
        c.opcode=WRS_HEARTBEAT;assert(WRS_Apply(&e,&c,i*10)==WRS_OK);
        assert(WRS_BeginCycle(&e,i*10)==(i>=300&&i<800?180:0));count[e.stage]++;
        assert(!e.reset_pi);
        if(i==450){c.opcode=WRS_START;assert(WRS_Apply(&e,&c,i*10)==WRS_OK);assert(e.index==450);}
        WRS_EndCycle(&e);
    }
    assert(count[0]==300&&count[1]==500&&count[2]==300);assert(e.state==WRS_COMPLETE&&e.reset_pi);
    c.opcode=WRS_START;assert(WRS_Apply(&e,&c,12000)==WRS_OK);assert(e.state==WRS_COMPLETE);
    WRS_EngineInit(&e);c.opcode=WRS_ARM;c.step=50;c.pre_ms=1000;c.hold_ms=1000;c.post_ms=1000;
    assert(WRS_Apply(&e,&c,0xfffffff0u)==WRS_OK);assert(WRS_BeginCycle(&e,484)==0&&e.state==WRS_ARMED);
    WRS_BeginCycle(&e,485);assert(e.state==WRS_FAULT&&(e.faults&WRS_F_HEARTBEAT));
    c.opcode=WRS_CLEAR_FAULT;c.step=c.pre_ms=c.hold_ms=c.post_ms=0;assert(WRS_Apply(&e,&c,486)==WRS_OK&&e.state==WRS_IDLE);
    c.run_id=8;c.opcode=WRS_ARM;c.step=50;c.pre_ms=c.hold_ms=c.post_ms=1000;assert(WRS_Apply(&e,&c,500)==WRS_OK);
    c.opcode=WRS_START;c.step=c.pre_ms=c.hold_ms=c.post_ms=0;assert(WRS_Apply(&e,&c,500)==WRS_OK);
    e.reset_pi=0;e.index=120;c.opcode=WRS_STOP;assert(WRS_Apply(&e,&c,500)==WRS_OK&&e.state==WRS_ZERO_POST&&!e.reset_pi);
    c.opcode=WRS_ABORT;assert(WRS_Apply(&e,&c,500)==WRS_OK&&e.state==WRS_FAULT&&e.reset_pi);
    memset(payload,0,16);WRS_Put32(payload,42);payload[4]=WRS_HELLO;
    assert(WRS_Frame(packet,WRS_COMMAND,payload,16)==26);
    for(i=0;i<26;i++)assert(WRS_ParseByte(&parser,packet[i],&parsed)==(i==25));assert(parsed.sequence==42&&parsed.opcode==WRS_HELLO);
    packet[24]^=1;for(i=0;i<26;i++)assert(!WRS_ParseByte(&parser,packet[i],&parsed));assert(parser.errors);
    packet[24]^=1;for(i=0;i<26;i++)WRS_ParseByte(&parser,packet[i],&parsed);assert(parsed.sequence==42);
    memset(&s,0,sizeof(s));s.sequence=0xffffffff;s.time_us=12345;s.dt_us=10000;s.run_id=7;s.state=2;s.stage=1;s.v=.18f;
    for(i=0;i<4;i++){s.target[i]=i*.125f;s.feedback[i]=i*.25f;s.pwm[i]=(int16_t)((int)i*-10);s.encoder[i]=(int16_t)((int)i*-20);}
    s.battery_mv=65535;s.faults=1;s.drops=12;s.misses=2;s.exec_us=65535;
    WRS_EncodeSample(payload,&s);WRS_Frame(packet,1,payload,84);
    for(i=0;i<94;i++)printf("%02x",packet[i]);puts("");puts("synthetic firmware checks passed");return 0;
}
