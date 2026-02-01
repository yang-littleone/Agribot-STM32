#ifndef __DATA_H
#define __DATA_H

#include "main.h"
#include "CarControl.h"
#include "ICM20948.h"

// 用户调用函数：

#define DATA_STK_SIZE 512
#define DATA_TASK_PRIO 4

#define FRAME_HEADER 0X7B // Frame_header //帧头
#define FRAME_TAIL 0X7D	  // Frame_tail   //帧尾
#define SEND_DATA_SIZE 24
#define RECEIVE_DATA_SIZE 11

#define AutoCharge_HEADER 0X7C // Frame_header //帧头
#define AutoCharge_TAIL 0X7F   // Frame_tail   //帧尾
#define AutoCharge_DATA_SIZE 8

/*****A structure for storing triaxial data of a gyroscope accelerometer*****/
/*****用于存放陀螺仪加速度计三轴数据的结构体*********************************/
typedef struct
{
	short X_data; // 2 bytes //2个字节
	short Y_data; // 2 bytes //2个字节
	short Z_data; // 2 bytes //2个字节
} IMUData_t;

/*******The structure of the serial port sending data************/
/*******串口发送数据的结构体*************************************/
typedef struct
{
	unsigned char Frame_Header; // 1个字节
	short X_speed;				// 2 bytes //2个字节
	short Y_speed;				// 2 bytes //2个字节
	short Z_speed;				// 2 bytes //2个字节
	short Power_Voltage;		// 2 bytes //2个字节
	IMUData_t Accelerometer;	// 6 bytes //6个字节
	IMUData_t Gyroscope;		// 6 bytes //6个字节
	unsigned char Frame_Tail;	// 1 bytes //1个字节

} SensorData_t;

typedef struct
{
	unsigned char buffer[SEND_DATA_SIZE];
	SensorData_t SensorData;
} SendData_t;

typedef struct
{
	unsigned char buffer[AutoCharge_DATA_SIZE];
	struct _AutoCharge_Str_
	{
		unsigned char Frame_Header; // 1 bytes //1个字节
		short Charging_Current;		// 2 bytes //2个字节
		unsigned char RED;			// 1 bytes //1个字节
		unsigned char Charging;		// 1 bytes //1个字节
		unsigned char yuliu;		// 1 bytes //1个字节
		unsigned char Frame_Tail;	// 1 bytes //1个字节
	} AutoCharge_Str;
} SEND_AutoCharge_DATA;

// typedef struct
// {
// 	unsigned char Frame_Header; // 1 bytes //1个字节
// 	float X_speed;				// 4 bytes //4个字节
// 	float Y_speed;				// 4 bytes //4个字节
// 	float Z_speed;				// 4 bytes //4个字节
// 	unsigned char Frame_Tail;	// 1 bytes //1个字节
// } ControlData_t;

typedef struct
{
	unsigned char buffer[RECEIVE_DATA_SIZE];
	MoveSpeed_t MoveSpeed;
} ReceiveData_t;

void DataTransfer(SendData_t *pSendData, Robot_t *pRobot, const IMU_DATA_t *pIMUData, const float *pVolt);
void DataRecive_Init(void);

static uint8_t Check_Sum(uint8_t *pBuffer, uint8_t Count_Number);
// void data_task(void *pvParameters);
// void data_transition(void);
// void USART1_SEND(void);
// void USART3_SEND(void);
// void USART3_Return(void);
// void USART2_Return(void);
// void USART5_SEND(void);

// void CAN_SEND(void);
// void uart1_init(uint32_t bound);
// void uart2_init(uint32_t bound);
// void uart3_init(uint32_t bound);
// void uart5_init(uint32_t bound);

// int USART1_IRQHandler(void);
// int USART2_IRQHandler(void);
// int USART3_IRQHandler(void);
// int UART5_IRQHandler(void);

// float Vz_to_Akm_Angle(float Vx, float Vz);
// float XYZ_Target_Speed_transition(uint8_t High,uint8_t Low);
// void usart1_send(uint8_t data);
// void usart2_send(uint8_t data);
// void usart3_send(uint8_t data);
// void usart5_send(uint8_t data);

// uint8_t Check_Sum(unsigned char Count_Number,unsigned char Mode);
// uint8_t Check_Sum_AutoCharge(unsigned char Count_Number,unsigned char Mode);
// uint8_t AT_Command_Capture(uint8_t uart_recv);
// void _System_Reset_(uint8_t uart_recv);

// extern uint8_t FlashWriteFlag;

#endif
