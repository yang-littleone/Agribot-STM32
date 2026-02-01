#ifndef __CARCONTROL_H
#define __CARCONTROL_H

#include "main.h"
#include "ICM20948.h"
#include "WiredPS2_gamepad.h"
#include "Encoder.h"
#include "system.h"
// 移除对Data.h的包含，使用前向声明解决循环依赖

#define PI 3.1415926f

#define MOTOR_REDUCTION_RATIO 30.0f                      // 减速比
#define ENCODER_PPR 500.0f                               // 编码器线束
#define ENCODER_PALUS 4                                  // 编码器模式3，一次四个脉冲
#define ENCODER_RESOLUTION (ENCODER_PPR * ENCODER_PALUS) // 编码器分辨率
#define WHEEL_DIAMETER 0.065f                            // 车轮直径，单位：m
#define WHEEL_PERIMETER (WHEEL_DIAMETER * PI)            // 车轮周长，单位：m
#define WHEEL_SPACING 0.187f                             // 车轮间距，单位：m
#define AXLE_SPACING 0.173f                              // 车轴间距，单位：m
#define CONTROL_PERIOD 0.01f                             // 控制周期，单位：s

typedef struct
{
    float Velocity;    // 电机实时速度，单位：m/s
    float Motor_PWM;   // 电机PWM数值，控制电机实时速度
    float Target;      // 电机目标速度值，控制电机目标速度
    float Velocity_KP; // 速度控制PID参数
    float Velocity_KI; // 速度控制PID参数
    float Bias;        // 偏差
    float Last_bias;   // 上一次偏差
} MotorParam_t;

typedef struct
{
    float X_Speed; // 小车X轴目标速度，单位：m/s
    float Y_Speed; // 小车Y轴目标速度，单位：m/s
    float Z_Speed; // 小车Z轴目标速度，单位：m/s
} MoveSpeed_t;

typedef struct
{
    MotorParam_t MotorA;
    MotorParam_t MotorB;
    MotorParam_t MotorC;
    MotorParam_t MotorD;
    MoveSpeed_t MoveSpeed;
} Robot_t;



typedef enum
{
    ROS_CONTROL,
    PS2_CONTROL,
    BLUE_CONTROL,
} ControlMode_t;

void GetVelocityFromEncoder(Robot_t *pRobot);
void VelocityPIDControl(Robot_t *pRobot);
float target_limit_float(float insert, float low, float high);
void InverseKinematic(Robot_t *pRobot);
void ForwardKinematics(Robot_t *pRobot);
void PS2_control(Robot_t *pRobot);
void ROS_Control(Robot_t *pRobot, MoveSpeed_t *pMoveSpeed);

static void Incremental_PI(MotorParam_t *pMotorParam);

#endif
