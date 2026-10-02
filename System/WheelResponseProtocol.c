#include "WheelResponseProtocol.h"
#include <string.h>
uint16_t WRS_CRC(const uint8_t *p, size_t n) {
    uint16_t crc=0xffff; size_t i; unsigned j;
    for(i=0;i<n;i++) { crc^=(uint16_t)p[i]<<8;
        for(j=0;j<8;j++) crc=(uint16_t)((crc&0x8000)?(crc<<1)^0x1021:crc<<1);
    } return crc;
}
void WRS_Put16(uint8_t *p,uint16_t v){p[0]=(uint8_t)v;p[1]=(uint8_t)(v>>8);}
void WRS_Put32(uint8_t *p,uint32_t v){unsigned i;for(i=0;i<4;i++)p[i]=(uint8_t)(v>>(8*i));}
uint16_t WRS_Get16(const uint8_t *p){return (uint16_t)(p[0]|((uint16_t)p[1]<<8));}
uint32_t WRS_Get32(const uint8_t *p){return p[0]|((uint32_t)p[1]<<8)|((uint32_t)p[2]<<16)|((uint32_t)p[3]<<24);}
static void putfloat(uint8_t *p,float f){uint32_t v;memcpy(&v,&f,4);WRS_Put32(p,v);}
uint16_t WRS_Frame(uint8_t *out,uint8_t type,const uint8_t *payload,uint16_t n){
    memcpy(out,"WRS1",4);out[4]=1;out[5]=type;WRS_Put16(out+6,n);
    if(n)memmove(out+8,payload,n);
    WRS_Put16(out+8+n,WRS_CRC(out,8+n));return (uint16_t)(n+10);
}
void WRS_EncodeSample(uint8_t *p,const WRS_Sample *s){unsigned i;
    WRS_Put32(p,s->sequence);WRS_Put32(p+4,s->time_us);WRS_Put32(p+8,s->dt_us);
    WRS_Put16(p+12,s->run_id);p[14]=s->state;p[15]=s->stage;
    putfloat(p+16,s->v);putfloat(p+20,s->w);
    for(i=0;i<4;i++){putfloat(p+24+4*i,s->target[i]);putfloat(p+40+4*i,s->feedback[i]);
        WRS_Put16(p+56+2*i,(uint16_t)s->pwm[i]);WRS_Put16(p+64+2*i,(uint16_t)s->encoder[i]);}
    WRS_Put16(p+72,s->battery_mv);WRS_Put16(p+74,s->faults);WRS_Put32(p+76,s->drops);
    WRS_Put16(p+80,s->misses);WRS_Put16(p+82,s->exec_us);
}
/* Bound memory and re-search magic after every rejected header or CRC. */
int WRS_ParseByte(WRS_Parser *p,uint8_t b,WRS_Command *c){
    if(p->used==26){memmove(p->bytes,p->bytes+1,25);p->used=25;}
    p->bytes[p->used++]=b;
    while(p->used>=4){
        if(memcmp(p->bytes,"WRS1",4)!=0){memmove(p->bytes,p->bytes+1,--p->used);continue;}
        if(p->used<8)return 0;
        if(p->bytes[4]!=1||p->bytes[5]!=16||WRS_Get16(p->bytes+6)!=16){
            p->errors++;memmove(p->bytes,p->bytes+1,--p->used);continue;}
        if(p->used<26)return 0;
        if(WRS_CRC(p->bytes,24)!=WRS_Get16(p->bytes+24)){
            p->errors++;memmove(p->bytes,p->bytes+1,--p->used);continue;}
        c->sequence=WRS_Get32(p->bytes+8);c->opcode=p->bytes[12];c->reserved=p->bytes[13];
        c->run_id=WRS_Get16(p->bytes+14);c->step=WRS_Get16(p->bytes+16);
        c->pre_ms=WRS_Get16(p->bytes+18);c->hold_ms=WRS_Get16(p->bytes+20);c->post_ms=WRS_Get16(p->bytes+22);
        p->used=0;return 1;
    } return 0;
}
