#include "MyTask.h"
#include "GetVolt.h"
#include "Data.h"

// 频率常量定义
#define RATE_2_HZ 2
#define RATE_20_HZ 20
#define RATE_100_HZ 100

QueueHandle_t g_EncoderQueue;

extern SemaphoreHandle_t g_TimeSemaphore;
extern QueueHandle_t g_IMUQueue;
extern QueueHandle_t g_VoltQueue;
extern QueueHandle_t g_RobotQueue;


ReceiveData_t ReceiveData = {0};

ControlMode_t ControlMode = ROS_CONTROL;

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
  uint8_t Time = 0;
  while (1)
  {
    // 此任务以2Hz的频率运行
    vTaskDelayUntil(&lastWakeTime, F2T(RATE_2_HZ));
    PEout(8) = !PEin(8);
    Time < 2 ? (PAout(8) = 1, Time++) : (PAout(8) = 0);
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

    xQueueReceive(g_RobotQueue, &Robot, 0);
    //    xQueuePeek(g_EncoderQueue, &Robot, 0);
    //    curcle = (double)EncoderCount / 500 / 4 / 30 * 100;
    OLED_Printf(0, 16, OLED_6X8, "PS2_ON_Flag:%d ", PS2_ON_Flag);
    // OLED_Printf(0, 0, OLED_6X8, "accel:%.2f %.2f %.2f        ", (float)IMU.accel.x / 1672.0f, (float)IMU.accel.y / 1672.0f, (float)IMU.accel.z / 1672.0f);
    // OLED_Printf(0, 8, OLED_6X8, "gyro:%.2f %.2f %.2f        ", (float)IMU.gyro.x / 3753.0f, (float)IMU.gyro.y / 3753.0f, (float)IMU.gyro.z / 3753.0f);
    OLED_Printf(0, 0, OLED_6X8, "A:%.2fm/s B:%.2fm/s        ", (float)Robot.MotorA.Velocity, (float)Robot.MotorB.Velocity);
    OLED_Printf(0, 8, OLED_6X8, "C:%.2fm/s D:%.2fm/s        ", (float)Robot.MotorC.Velocity, (float)Robot.MotorD.Velocity);
    float volt = GetVoltValue();
    OLED_Printf(0, 24, OLED_6X8, "Volt:%.2fV        ", volt);
    OLED_Printf(0,32, OLED_6X8, "StartFlag:%d        ", GamePadInterface->StartFlag);
    OLED_Printf(0,40, OLED_6X8, "carmode:%d        ", ControlMode);
    // 将电压值发送给数据处理任务
    xQueueOverwrite(g_VoltQueue, &volt);
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
// extern uint8_t ReceiveData[8];

void DataTask(void *pvParameters)
{
  // DataRecive_Init();
  uint32_t lastWakeTime = getSysTickCnt();

  // 定义发送数据结构体
  SendData_t SendData;
  memset(&SendData, 0, sizeof(SendData_t));

  Robot_t Robot;
  memset(&Robot, 0, sizeof(Robot_t));

  IMU_DATA_t IMU;
  memset(&IMU, 0, sizeof(IMU_DATA_t));

  float volt = 0.0f;

  char *str = "hello world\r\n";
  while (1)
  {
    // 此任务以20Hz的频率运行
    vTaskDelayUntil(&lastWakeTime, F2T(RATE_20_HZ));
    xQueueReceive(g_IMUQueue, &IMU, 0);
    xQueueReceive(g_VoltQueue, &volt, 0);
    xQueueReceive(g_RobotQueue, &Robot, 0);
    DataTransfer(&SendData, &Robot, &IMU, &volt);
    // printf("X1_Speed:%.2f Y1_Speed:%.2f Z1_Speed:%.2f\r\n", Robot.MoveSpeed.X_Speed, Robot.MoveSpeed.Y_Speed, Robot.MoveSpeed.Z_Speed);
    // HAL_UART_Transmit_IT(&huart3, (uint8_t *)SendData.buffer, SEND_DATA_SIZE);
  }
}

void ICM20948Task(void *pvParameters)
{
  uint32_t lastWakeTime = getSysTickCnt();
  invMSInit();
  //  ICM20948_Get_Accel(&IMU); // 得到加速度传感器数据

  uint16_t Time_CNT = 0;
  // Get gyroscope data
  //  ICM20948_Get_Gyroscope(&IMU); // 得到陀螺仪数据
  //  ImuData_copy(&IMU.Deviation_gyro, &IMU.gyro);
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
    // printf("X_Speed:%x Y_Speed:%x Z_Speed:%x\r\n", IMU.accel.x, IMU.accel.y, IMU.accel.z);
    // printf("accel:%.2f %.2f %.2f        ", (float)IMU.accel.x / 1672.0f, (float)IMU.accel.y / 1672.0f, (float)IMU.accel.z / 1672.0f);

    xQueueOverwrite(g_IMUQueue, &IMU);
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
  DataRecive_Init();
  Robot_t Robot;
  memset(&Robot, 0, sizeof(Robot_t));

  IMUData_t IMUData;
  memset(&IMUData, 0, sizeof(IMUData_t));

  // xSemaphoreTake(g_TimeSemaphore, portMAX_DELAY);

  while (1)
  {
    // 此任务以100Hz的频率运行,ms 为10ms
    vTaskDelayUntil(&lastWakeTime, F2T(RATE_100_HZ));
    // 获取电机的速度
    GetVelocityFromEncoder(&Robot);

    switch (ControlMode)
    {
    case PS2_CONTROL:
      PS2_control(&Robot);
      break;
    case ROS_CONTROL:
      ROS_Control(&Robot, &ReceiveData.MoveSpeed);
      break;

    default:
      break;
    }
    // PS2_control(&Robot, &IMU);
    // ROS_Control(&Robot, &ReceiveData.MoveSpeed);

    xQueueOverwrite(g_RobotQueue, &Robot);
  }
}
