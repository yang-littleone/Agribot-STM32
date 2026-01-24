#include "Encoder.h"

/* 电机A的编码器定时器为TIM2 ，编码器A为TIM2 CH2，编码器B为TIM2 CH1 */
/* 电机B的编码器定时器为TIM3 ，编码器A为TIM3 CH2，编码器B为TIM3 CH1 */
/* 电机C的编码器定时器为TIM4 ，编码器A为TIM4 CH2，编码器B为TIM4 CH1 */
/* 电机D的编码器定时器为TIM5 ，编码器A为TIM5 CH2，编码器B为TIM5 CH1 */

#define ENCODERA_HANDLE htim2
#define ENCODERB_HANDLE htim3
#define ENCODERC_HANDLE htim4
#define ENCODERD_HANDLE htim5

/**
 * @brief  初始化编码器
 * @param  无
 * @retval 无
 */
void Encoder_Init(void)
{
    // Start the encoder interface for motor A
    HAL_TIM_Encoder_Start(&ENCODERA_HANDLE, TIM_CHANNEL_ALL);
    // Start the encoder interface for motor B
    HAL_TIM_Encoder_Start(&ENCODERB_HANDLE, TIM_CHANNEL_ALL);
    // Start the encoder interface for motor C
    HAL_TIM_Encoder_Start(&ENCODERC_HANDLE, TIM_CHANNEL_ALL);
    // Start the encoder interface for motor D
    HAL_TIM_Encoder_Start(&ENCODERD_HANDLE, TIM_CHANNEL_ALL);
}

// according to motor_id to get encoder count
/**
 * @brief  根据电机ID获取编码器计数
 * @param  Motor_ID，电机ID，范围：'A'~'D'
 * @retval 编码器计数
 */
int Encoder_GetCount(char Motor_ID)
{
    int count = 0;
    switch (Motor_ID)
    {
		//计数器只有 0~65535 的无符号范围，反向计数时从 65535 递减，无法直接表示负数
		//所以使用short强制类型转换
    case 'A':
        count = (short)__HAL_TIM_GET_COUNTER(&ENCODERA_HANDLE); // 获取编码器计数值
        __HAL_TIM_SET_COUNTER(&ENCODERA_HANDLE, 0);      // 重置编码器计数值
        break;
    case 'B':
        count = (short)__HAL_TIM_GET_COUNTER(&ENCODERB_HANDLE);
        __HAL_TIM_SET_COUNTER(&ENCODERB_HANDLE, 0);
        break;
    case 'C':
        count = (short)__HAL_TIM_GET_COUNTER(&ENCODERC_HANDLE);
        __HAL_TIM_SET_COUNTER(&ENCODERC_HANDLE, 0);
        break;
    case 'D':
        count = (short)__HAL_TIM_GET_COUNTER(&ENCODERD_HANDLE);
        __HAL_TIM_SET_COUNTER(&ENCODERD_HANDLE, 0);
        break;
    default:
        break;
    }
    return count;
}