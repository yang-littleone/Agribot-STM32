#include "Data.h"
#include "usart.h"
#include "main.h"

void DataTransfer(SendData_t *pSendData, Robot_t *pRobot, const IMU_DATA_t *pIMUData, const float *pVolt)
{
    // Robot_t Robot = *pRobot;

    pSendData->SensorData.Frame_Header = FRAME_HEADER;
    pSendData->SensorData.Frame_Tail = FRAME_TAIL;

    // 运动学正解
    ForwardKinematics(pRobot);

    pSendData->SensorData.X_speed = (short)(pRobot->MoveSpeed.X_Speed * 1000); // 转换为mm/s
    pSendData->SensorData.Y_speed = 0;
    pSendData->SensorData.Z_speed = (short)(pRobot->MoveSpeed.Z_Speed * 1000); // 转换为mm/s

    pSendData->SensorData.Accelerometer.X_data = pIMUData->accel.y; // 传感器坐标系与小车坐标系转换
    pSendData->SensorData.Accelerometer.Y_data = -pIMUData->accel.x; // 传感器坐标系与小车坐标系转换
    pSendData->SensorData.Accelerometer.Z_data = pIMUData->accel.z;

    pSendData->SensorData.Gyroscope.X_data = pIMUData->gyro.y; // 传感器坐标系与小车坐标系转换
    pSendData->SensorData.Gyroscope.Y_data = -pIMUData->gyro.x; // 传感器坐标系与小车坐标系转换
    pSendData->SensorData.Gyroscope.Z_data = pIMUData->gyro.z;

    pSendData->SensorData.Power_Voltage = (short)(*pVolt * 1000); // 转换为mV

    pSendData->buffer[0] = pSendData->SensorData.Frame_Header;
    pSendData->buffer[1] = 0;

    // The three-axis speed of / / car is split into two eight digit Numbers
    // 小车三轴速度,各轴都拆分为两个8位数据再发送
    pSendData->buffer[2] = pSendData->SensorData.X_speed >> 8;
    pSendData->buffer[3] = pSendData->SensorData.X_speed;
    pSendData->buffer[4] = pSendData->SensorData.Y_speed >> 8;
    pSendData->buffer[5] = pSendData->SensorData.Y_speed;
    pSendData->buffer[6] = pSendData->SensorData.Z_speed >> 8;
    pSendData->buffer[7] = pSendData->SensorData.Z_speed;

    // The acceleration of the triaxial axis of / / imu accelerometer is divided into two eight digit reams
    // IMU加速度计三轴加速度,各轴都拆分为两个8位数据再发送
    pSendData->buffer[8] = pSendData->SensorData.Accelerometer.X_data >> 8;
    pSendData->buffer[9] = pSendData->SensorData.Accelerometer.X_data;
    pSendData->buffer[10] = pSendData->SensorData.Accelerometer.Y_data >> 8;
    pSendData->buffer[11] = pSendData->SensorData.Accelerometer.Y_data;
    pSendData->buffer[12] = pSendData->SensorData.Accelerometer.Z_data >> 8;
    pSendData->buffer[13] = pSendData->SensorData.Accelerometer.Z_data;

    // The axis of the triaxial velocity of the / /imu is divided into two eight digits
    // IMU角速度计三轴角速度,各轴都拆分为两个8位数据再发送
    pSendData->buffer[14] = pSendData->SensorData.Gyroscope.X_data >> 8;
    pSendData->buffer[15] = pSendData->SensorData.Gyroscope.X_data;
    pSendData->buffer[16] = pSendData->SensorData.Gyroscope.Y_data >> 8;
    pSendData->buffer[17] = pSendData->SensorData.Gyroscope.Y_data;
    pSendData->buffer[18] = pSendData->SensorData.Gyroscope.Z_data >> 8;
    pSendData->buffer[19] = pSendData->SensorData.Gyroscope.Z_data;

    // Battery voltage, split into two 8 digit Numbers
    // 电池电压,拆分为两个8位数据发送
    pSendData->buffer[20] = pSendData->SensorData.Power_Voltage >> 8;
    pSendData->buffer[21] = pSendData->SensorData.Power_Voltage;

    pSendData->buffer[22] = Check_Sum(pSendData->buffer, 22);
    pSendData->buffer[23] = pSendData->SensorData.Frame_Tail;
}

// 异或校验
static uint8_t Check_Sum(uint8_t *pBuffer, uint8_t Count_Number)
{
    unsigned char check_sum = 0, k;

    // Validate the data to be sent
    // 对数据进行校验
    for (k = 0; k < Count_Number; k++)
    {
        check_sum = check_sum ^ pBuffer[k];
    }

    return check_sum;
}

extern ReceiveData_t ReceiveData;
uint8_t ReceiveDataTemp = 0;

void DataRecive_Init(void)
{
    HAL_UART_Receive_IT(&huart3, (uint8_t *)&ReceiveDataTemp, 1);
}

// #include "CarControl.h"
extern ControlMode_t ControlMode;

void HAL_UART_RxCpltCallback(UART_HandleTypeDef *huart)
{
    static uint8_t count = 0;
    static uint8_t status = 0;
    if (huart->Instance == USART3)
    {
        /* code */
        HAL_UART_Receive_IT(&huart3, (uint8_t *)&ReceiveDataTemp, 1);

        if (count == 0 && ReceiveDataTemp == FRAME_HEADER && status == 0)
        {
            ReceiveData.buffer[count] = ReceiveDataTemp;
            count++;
            status = 1;
        }
        else if (status == 1)
        {
            ReceiveData.buffer[count] = ReceiveDataTemp;
            count++;
            if (count == 11)
            {
                status = 0;
                count = 0;
                if (Check_Sum(ReceiveData.buffer, 9) == ReceiveData.buffer[9] && ReceiveData.buffer[10] == FRAME_TAIL)
                {
                    if (ControlMode != ROS_CONTROL)
                        ControlMode = ROS_CONTROL;
                    ReceiveData.MoveSpeed.X_Speed = (ReceiveData.buffer[3] << 8 | ReceiveData.buffer[4]) / 1000.0f;
                    ReceiveData.MoveSpeed.Y_Speed = (ReceiveData.buffer[5] << 8 | ReceiveData.buffer[6]) / 1000.0f;
                    ReceiveData.MoveSpeed.Z_Speed = (ReceiveData.buffer[7] << 8 | ReceiveData.buffer[8]) / 1000.0f;
                }
            }
        }

        // if (ReceiveData.buffer[0] == FRAME_HEADER && ReceiveData.buffer[10] == FRAME_TAIL)
        // {
        //     if (Check_Sum(ReceiveData.buffer, 9) == ReceiveData.buffer[9])
        //     {
        //         if (ControlMode != ROS_CONTROL)
        //             ControlMode = ROS_CONTROL;
        //         ReceiveData.MoveSpeed.X_Speed = (ReceiveData.buffer[3] << 8 | ReceiveData.buffer[4]) / 1000.0f;
        //         ReceiveData.MoveSpeed.Y_Speed = (ReceiveData.buffer[5] << 8 | ReceiveData.buffer[6]) / 1000.0f;
        //         ReceiveData.MoveSpeed.Z_Speed = (ReceiveData.buffer[7] << 8 | ReceiveData.buffer[8]) / 1000.0f;
        //         HAL_UART_Transmit_IT(&huart3, (uint8_t *)ReceiveData.buffer, 11);
        //     }
        // }
        // HAL_UART_Transmit_IT(&huart3, (uint8_t *)ReceiveData, 8);
    }
}
