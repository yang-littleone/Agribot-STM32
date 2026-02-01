#ifndef __MYTASK_H
#define __MYTASK_H

#include "main.h"
#include "system.h"
#include "sys.h"
#include "ICM20948.h"
#include "CarControl.h"
#include "FreeRTOS.h"
#include "task.h"
#include "queue.h"
#include "semphr.h"
#include "OLED.h"
#include "usart.h"

// 用户调用函数：
void LedTask(void *argument);
void ShowTask(void *argument);
void DataTask(void *pvParameters);
void ICM20948Task(void *pvParameters);
void CarControlTask(void const *argument);

#define IMU_TASK_PRIO 3
#define IMU_STK_SIZE 256
#define IMU_TASK_RATE RATE_100_HZ

#endif
