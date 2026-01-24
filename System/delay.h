#ifndef __DELAY_H
#define __DELAY_H 			     

#include "main.h"

uint32_t getSysTickCnt(void);
void delay_init(uint8_t SYSCLK);
void delay_us(uint32_t nus);
void delay_ms(uint32_t nms);
void delay_xms(uint32_t nms);
#endif





























