#ifndef __ENCODER_H
#define __ENCODER_H

#include "main.h"
#include "tim.h"

// define encoder structure, A~D represents four motors
typedef struct
{
    int A;
    int B;
    int C;
    int D;
} Encoder_t;

// 用户调用函数：
void Encoder_Init(void);
int Encoder_GetCount(char Motor_ID);
#endif
