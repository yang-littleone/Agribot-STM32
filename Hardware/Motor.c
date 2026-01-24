#include "motor.h"

/*四个电机，左后为A，左前为B，右后为D，右前为C*/

#define PWMA1(x) __HAL_TIM_SET_COMPARE(&htim11, TIM_CHANNEL_1, x)
#define PWMA2(x) __HAL_TIM_SET_COMPARE(&htim10, TIM_CHANNEL_1, x)

#define PWMB1(x) __HAL_TIM_SET_COMPARE(&htim9, TIM_CHANNEL_1, x)
#define PWMB2(x) __HAL_TIM_SET_COMPARE(&htim9, TIM_CHANNEL_2, x)

#define PWMC1(x) __HAL_TIM_SET_COMPARE(&htim1, TIM_CHANNEL_2, x)
#define PWMC2(x) __HAL_TIM_SET_COMPARE(&htim1, TIM_CHANNEL_1, x)

#define PWMD1(x) __HAL_TIM_SET_COMPARE(&htim1, TIM_CHANNEL_4, x)
#define PWMD2(x) __HAL_TIM_SET_COMPARE(&htim1, TIM_CHANNEL_3, x)

void Motor_Init(void)
{
    // Motor A PWM Start
    HAL_TIM_PWM_Start(&htim11, TIM_CHANNEL_1);
    HAL_TIM_PWM_Start(&htim10, TIM_CHANNEL_1);
    // Motor B PWM Start
    HAL_TIM_PWM_Start(&htim9, TIM_CHANNEL_1);
    HAL_TIM_PWM_Start(&htim9, TIM_CHANNEL_2);
    // Motor C PWM Start
    HAL_TIM_PWM_Start(&htim1, TIM_CHANNEL_2);
    HAL_TIM_PWM_Start(&htim1, TIM_CHANNEL_1);
    // Motor D PWM Start
    HAL_TIM_PWM_Start(&htim1, TIM_CHANNEL_4);
    HAL_TIM_PWM_Start(&htim1, TIM_CHANNEL_3);
}
void MotorA_ON(void)
{
    PWMA2(_MAX_COMPARE - (_MAX_COMPARE) * 0.2);
    PWMA1(_MAX_COMPARE);
}

/**
 * @brief  Set the PWM of the four motors
 * @param  Motor_A: PWM of motor A
 * @param  Motor_B: PWM of motor B
 * @param  Motor_C: PWM of motor C
 * @param  Motor_D: PWM of motor D
 * @retval None
 */
void Set_PWM(int Motor_A, int Motor_B, int Motor_C, int Motor_D)
{
    // Forward and reverse control of motor
    // 电机正反转控制
    if (Motor_A < 0)
        PWMA1(_MAX_COMPARE), PWMA2(_MAX_COMPARE + Motor_A);
    else
        PWMA1(_MAX_COMPARE - Motor_A), PWMA2(_MAX_COMPARE);

    // Forward and reverse control of motor
    // 电机正反转控制
    if (Motor_B < 0)
        PWMB1(_MAX_COMPARE), PWMB2(_MAX_COMPARE + Motor_B);
    else
        PWMB1(_MAX_COMPARE - Motor_B), PWMB2(_MAX_COMPARE);
    //  PWMB1=10000,PWMB2=5000;

    // Forward and reverse control of motor
    // 电机正反转控制
    if (Motor_C < 0)
        PWMC1(_MAX_COMPARE), PWMC2(_MAX_COMPARE + Motor_C);
    else
        PWMC1(_MAX_COMPARE - Motor_C), PWMC2(_MAX_COMPARE);

    // Forward and reverse control of motor
    // 电机正反转控制
    if (Motor_D < 0)
        PWMD1(_MAX_COMPARE), PWMD2(_MAX_COMPARE + Motor_D);
    else
        PWMD1(_MAX_COMPARE - Motor_D), PWMD2(_MAX_COMPARE);

    // // Servo control
    // // 舵机控制
    // Servo_PWM = servo;
}
