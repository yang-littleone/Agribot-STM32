#ifndef __DATA_H
#define __DATA_H

#include "main.h"

//用户调用函数：

#define DATA_STK_SIZE   512 
#define DATA_TASK_PRIO  4

#define FRAME_HEADER      0X7B //Frame_header //帧头
#define FRAME_TAIL        0X7D //Frame_tail   //帧尾
#define SEND_DATA_SIZE    24
#define RECEIVE_DATA_SIZE 11

#define AutoCharge_HEADER      0X7C //Frame_header //帧头
#define AutoCharge_TAIL        0X7F //Frame_tail   //帧尾
#define AutoCharge_DATA_SIZE    8

/*****A structure for storing triaxial data of a gyroscope accelerometer*****/
/*****用于存放陀螺仪加速度计三轴数据的结构体*********************************/
typedef struct __Mpu6050_Data_ 
{
	short X_data; //2 bytes //2个字节
	short Y_data; //2 bytes //2个字节
	short Z_data; //2 bytes //2个字节
}Mpu6050_Data;

/*******The structure of the serial port sending data************/
/*******串口发送数据的结构体*************************************/
typedef struct _SEND_DATA_  
{
	unsigned char buffer[SEND_DATA_SIZE];
	struct _Sensor_Str_
	{
		unsigned char Frame_Header; //1个字节
		short X_speed;	            //2 bytes //2个字节
		short Y_speed;              //2 bytes //2个字节
		short Z_speed;              //2 bytes //2个字节
		short Power_Voltage;        //2 bytes //2个字节
		Mpu6050_Data Accelerometer; //6 bytes //6个字节
		Mpu6050_Data Gyroscope;     //6 bytes //6个字节	
		unsigned char Frame_Tail;   //1 bytes //1个字节
	}Sensor_Str;
}SEND_DATA;

typedef struct _SEND_AutoCharge_DATA_  
{
	unsigned char buffer[AutoCharge_DATA_SIZE];
	struct _AutoCharge_Str_
	{
		unsigned char Frame_Header; //1 bytes //1个字节
		short Charging_Current;	    //2 bytes //2个字节
		unsigned char RED;          //1 bytes //1个字节
		unsigned char Charging;     //1 bytes //1个字节
		unsigned char yuliu;		//1 bytes //1个字节
		unsigned char Frame_Tail;   //1 bytes //1个字节
	}AutoCharge_Str;
}SEND_AutoCharge_DATA;

typedef struct _RECEIVE_DATA_  
{
	unsigned char buffer[RECEIVE_DATA_SIZE];
	struct _Control_Str_
	{
		unsigned char Frame_Header; //1 bytes //1个字节
		float X_speed;	            //4 bytes //4个字节
		float Y_speed;              //4 bytes //4个字节
		float Z_speed;              //4 bytes //4个字节
		unsigned char Frame_Tail;   //1 bytes //1个字节
	}Control_Str;
}RECEIVE_DATA;


//void data_task(void *pvParameters);
//void data_transition(void);
//void USART1_SEND(void);
//void USART3_SEND(void);
//void USART3_Return(void);
//void USART2_Return(void);
//void USART5_SEND(void);

//void CAN_SEND(void);
//void uart1_init(uint32_t bound);
//void uart2_init(uint32_t bound);
//void uart3_init(uint32_t bound);
//void uart5_init(uint32_t bound);

//int USART1_IRQHandler(void);
//int USART2_IRQHandler(void);
//int USART3_IRQHandler(void);
//int UART5_IRQHandler(void);

//float Vz_to_Akm_Angle(float Vx, float Vz);
//float XYZ_Target_Speed_transition(uint8_t High,uint8_t Low);
//void usart1_send(uint8_t data);
//void usart2_send(uint8_t data);
//void usart3_send(uint8_t data);
//void usart5_send(uint8_t data);

//uint8_t Check_Sum(unsigned char Count_Number,unsigned char Mode);
//uint8_t Check_Sum_AutoCharge(unsigned char Count_Number,unsigned char Mode);
//uint8_t AT_Command_Capture(uint8_t uart_recv);
//void _System_Reset_(uint8_t uart_recv);

//extern uint8_t FlashWriteFlag;

#endif
