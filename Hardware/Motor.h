#ifndef __MOTOR_H
#define __MOTOR_H

#include "main.h"
#include "tim.h"

#define _MAX_COMPARE 16799

//用户调用函数：
void Motor_Init(void);
void MotorA_ON(void);
void Set_PWM(int Motor_A, int Motor_B, int Motor_C, int Motor_D);


#endif
