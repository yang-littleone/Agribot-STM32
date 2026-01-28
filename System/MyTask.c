#include "MyTask.h"
// #include "main.h"
//  #include "OLED.h"
//  #include "delay.h"
//  #include "MyTask.h"
//  #include "system.h"
//  #include "MyI2C.h"
//  #include "icm20948.h"
//  #include "FreeRTOS.h"
//  #include "task.h"
//  #include "FreeRTOSConfig.h"

// 频率常量定义
#define RATE_2_HZ 2
#define RATE_20_HZ 20
#define RATE_100_HZ 100

QueueHandle_t g_EncoderQueue;

extern SemaphoreHandle_t g_TimeSemaphore;
//
int encoderc = 0;
// 将频率转换为周期(以ticks为单位)的宏
#define F2T(freq) pdMS_TO_TICKS(1000 / (freq))

// imu数据结构体
// IMU_DATA_t imu;
uint8_t j = 5;
IMU_DATA_t IMU;

uint8_t IMU_ID = 0;
void LedTask(void *pvParameters)
{
  uint32_t lastWakeTime = getSysTickCnt();

  while (1)
  {
    // 此任务以2Hz的频率运行
    vTaskDelayUntil(&lastWakeTime, F2T(RATE_2_HZ));
    PEout(8) = !PEin(8);
  }
}

void ShowTask(void *pvParameters)
{
  OLED_Init();
  uint32_t lastWakeTime = getSysTickCnt();
  uint8_t i = 0;
  Robot_t Robot;
  memset(&Robot, 0, sizeof(Robot_t));

  double curcle = 0.0f;

  while (1)
  {
    // 此任务以2Hz的频率运行
    vTaskDelayUntil(&lastWakeTime, F2T(RATE_20_HZ));

    xQueueReceive(g_EncoderQueue, &Robot, 0);
    //    xQueuePeek(g_EncoderQueue, &Robot, 0);
    //    curcle = (double)EncoderCount / 500 / 4 / 30 * 100;
    OLED_Printf(0, 16, OLED_6X8, "PS2_ON_Flag:%d ", PS2_ON_Flag);
    // OLED_Printf(0, 0, OLED_6X8, "accel:%.2f %.2f %.2f        ", (float)IMU.accel.x / 1672.0f, (float)IMU.accel.y / 1672.0f, (float)IMU.accel.z / 1672.0f);
    // OLED_Printf(0, 8, OLED_6X8, "gyro:%.2f %.2f %.2f        ", (float)IMU.gyro.x / 3753.0f, (float)IMU.gyro.y / 3753.0f, (float)IMU.gyro.z / 3753.0f);
    OLED_Printf(0, 0, OLED_6X8, "A:%.2fm/s B:%.2fm/s        ", (float)Robot.MotorA.Velocity, (float)Robot.MotorB.Velocity);
    OLED_Printf(0, 8, OLED_6X8, "C:%.2fm/s D:%.2fm/s        ", (float)Robot.MotorC.Velocity, (float)Robot.MotorD.Velocity);
    
	  // 调试电机的时候显示四电机编码数据
    // OLED_Printf(0, 0, OLED_8X16, "A:%d B:%d     ", EncoderCount.A, EncoderCount.B);
    // OLED_Printf(0, 16, OLED_8X16, "C:%d D:%d      ", EncoderCount.C, EncoderCount.D);
    // OLED_Printf(0, 32, OLED_8X16, "A:%.2f B:%.2f", (float)EncoderCount.A / 500.0f / 4.0f / 30.0f * 100.0f, (float)EncoderCount.B / 500.0f / 4.0f / 30.0f * 100.0f);
    // OLED_Printf(0, 48, OLED_8X16, "C:%.2f D:%.2f    ", (float)EncoderCount.C / 500.0f / 4.0f / 30.0f * 100.0f, (float)EncoderCount.D / 500.0f / 4.0f / 30.0f * 100.0f);
    // 看当前任务剩余多少内存
    //	OLED_Printf(0, 48, OLED_8X16, "%d     ", uxTaskGetStackHighWaterMark(NULL));

    OLED_Update();
  }
}

void UsartTask(void *pvParameters)
{
  uint32_t lastWakeTime = getSysTickCnt();

  char *str = "hello world\r\n";
  while (1)
  {
    // 此任务以20Hz的频率运行
    vTaskDelayUntil(&lastWakeTime, F2T(RATE_2_HZ));
    //    printf("nihaoya!!\r\n");
    // HAL_UART_Transmit(&huart3, str, strlen(str), HAL_MAX_DELAY);
  }
}

void ICM20948Task(void *pvParameters)
{
  //  uint8_t ack;
  //  MyI2C_Start();
  //  MyI2C_SendByte(0xD0);
  //  IMU_ID = MyI2C_ReceiveAck();
  //  MyI2C_Stop();
  uint32_t lastWakeTime = getSysTickCnt();
  invMSInit();
  ICM20948_Get_Accel(&IMU); // 得到加速度传感器数据

  uint16_t Time_CNT = 0;
  // Get gyroscope data
  ICM20948_Get_Gyroscope(&IMU); // 得到陀螺仪数据
  ImuData_copy(&IMU.Deviation_gyro, &IMU.gyro);
  while (1)
  {
    vTaskDelayUntil(&lastWakeTime, F2T(RATE_100_HZ));
    if (Time_CNT++ <= 1000)
    {
      ImuData_copy(&IMU.Deviation_gyro, &IMU.gyro);
      ImuData_copy(&IMU.Deviation_accel, &IMU.accel);
    }
    else
      xSemaphoreGive(g_TimeSemaphore);

    // Get acceleration sensor data
    ICM20948_Get_Accel(&IMU); // 得到加速度传感器数据

    // Get gyroscope data
    ICM20948_Get_Gyroscope(&IMU); // 得到陀螺仪数据
  }
}

/**
 * @brief: 电机运动控制任务，整个小车运动的核心任务
 * @param: argument: 任务参数
 * @retval: None
 */
void CarControlTask(void const *argument)
{
  TickType_t lastWakeTime = xTaskGetTickCount();

  Motor_Init();
  Encoder_Init();
  Robot_t Robot;
  memset(&Robot, 0, sizeof(Robot_t));
  g_EncoderQueue = xQueueCreate(1, sizeof(Robot_t));
  // xSemaphoreTake(g_TimeSemaphore, portMAX_DELAY);
  // Set_PWM(_MAX_COMPARE, _MAX_COMPARE * 0.8, _MAX_COMPARE * 0.5, _MAX_COMPARE * 0.3);
  // Motor.MotorA.Target = -0.5;
  // Motor.MotorA.Velocity_KP = 800;
  // Motor.MotorA.Velocity_KI = 500.0f;
//	Robot.MoveSpeed.X_Speed = 0.5;
//	Robot.MoveSpeed.Y_Speed = 0;
//	Robot.MoveSpeed.Z_Speed = 0;
	
  while (1)
  {
    // 此任务以100Hz的频率运行,ms 为10ms
    vTaskDelayUntil(&lastWakeTime, F2T(RATE_100_HZ));
    // 获取电机的速度
    GetVelocityFromEncoder(&Robot);

    PS2_control(&Robot, &IMU);
    InverseKinematic(&Robot);
    VelocityPIDControl(&Robot);
    //   Incremental_PI(&Robot.MotorA);
    //  Set_PWM(Robot.MotorA.Motor_PWM, _MAX_COMPARE * 0.3, _MAX_COMPARE * 0.3, _MAX_COMPARE * 0.3);
    //printf("v:%.2f\n", Robot.MotorA.Velocity);
    // EncoderCount.A = Encoder_GetCount('A');
    // EncoderCount.B = Encoder_GetCount('B');
    // EncoderCount.C = Encoder_GetCount('C');
    // EncoderCount.D = Encoder_GetCount('D');
    xQueueOverwrite(g_EncoderQueue, &Robot);
  }
}

// void ICM20948_task(void *pvParameters)
//{
////  I2C_GPIOInit(); // 初始化IIC引脚
// invMSInit();
//   uint32_t lastWakeTime = getSysTickCnt();
//	IMU_ID = ICM20948_getDeviceID();
//   while (1)
//   {
//     // This task runs at 100Hz
//     // 此任务以100Hz的频率运行
//     vTaskDelayUntil(&lastWakeTime, IMU_TASK_RATE);

//    // Read the gyroscope zero before starting
//    // 开机前，读取陀螺仪零点
//    if (SysVal.Time_count < CONTROL_DELAY)
//    {
//      ImuData_copy(&imu.Deviation_gyro, &imu.gyro);
//      ImuData_copy(&imu.Deviation_accel, &imu.accel);
//    }

//    // Get acceleration sensor data
//    ICM20948_Get_Accel(); // 得到加速度传感器数据

//    // Get gyroscope data
//    j = ICM20948_Get_Gyroscope(); // 得到陀螺仪数据

// #if 0 // 未使用磁力计数据,不开启采集
//         static uint8_t mag_count=0;
//         //Get magnetometer data
//         mag_count++;
//         if(mag_count>=13)	 //磁力计最大采样速率为8hz，因此每进入这个函数13次才采样一次磁力计信息
//         {
//             invMSMagRead(&magnet[0], &magnet[1], &magnet[2]); //得到磁力计数据
//             mag_count=0;
//         }
// #endif
//   }
// }

///**************************************************************************
// 函数功能：复制imu的数值
// 入口参数：需要赋值的结构体变量，被复制的结构体变量
// 返回  值：无
// 作    者：WHEELTEC
//**************************************************************************/
// void ImuData_copy(IMU_BASE_t *req_val, const IMU_BASE_t *copied_val)
//{
//   req_val->x = copied_val->x;
//   req_val->y = copied_val->y;
//   req_val->z = copied_val->z;
// }
