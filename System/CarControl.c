#include "CarControl.h"
#include "Motor.h"

//#include "main.h"
/**
 * @brief 获取电机的速度
 * @param pMotor 电机结构体指针
 * @return void
 */
void GetVelocityFromEncoder(Robot_t *pRobot)
{
    Encoder_t EncoderCount;

    // 获取各个电机的编码器计数值
    EncoderCount.A = Encoder_GetCount('A');
    EncoderCount.B = Encoder_GetCount('B');
    EncoderCount.C = Encoder_GetCount('C');
    EncoderCount.D = Encoder_GetCount('D');

    // 获取编码器的计数值后，计算每个电机的速度
    // 速度计算公式：速度 = (编码器计数值 / 编码器分辨率) * (车轮周长) * (1 / 控制周期) / 减速比，其中，编码器分辨率 = 编码器PPR * 编码器模式脉冲数
    // (编码器计数值 / 编码器分辨率) / 减速比，表示电机在控制时间内转过的圈数，比如100hz控制周期0.01s内转过的圈数
    // 然后转换为一秒内转过的圈数，也就是乘以(1 / 控制周期)，圈/s
    // 最后乘以车轮周长，得到线速度，单位m/s
    pRobot->MotorA.Velocity = EncoderCount.A * (1 / CONTROL_PERIOD) * WHEEL_PERIMETER / (ENCODER_RESOLUTION * MOTOR_REDUCTION_RATIO);
    pRobot->MotorB.Velocity = EncoderCount.B * (1 / CONTROL_PERIOD) * WHEEL_PERIMETER / (ENCODER_RESOLUTION * MOTOR_REDUCTION_RATIO);
    pRobot->MotorC.Velocity = EncoderCount.C * (1 / CONTROL_PERIOD) * WHEEL_PERIMETER / (ENCODER_RESOLUTION * MOTOR_REDUCTION_RATIO);
    pRobot->MotorD.Velocity = EncoderCount.D * (1 / CONTROL_PERIOD) * WHEEL_PERIMETER / (ENCODER_RESOLUTION * MOTOR_REDUCTION_RATIO);
}
/**
根据增量式离散PID公式
pwm+=Kp[e（k）-e(k-1)]+Ki*e(k)+Kd[e(k)-2e(k-1)+e(k-2)]
e(k)代表本次偏差
e(k-1)代表上一次的偏差  以此类推
pwm代表增量输出
在我们的速度控制闭环系统里面，只使用PI控制
pwm+=Kp[e（k）-e(k-1)]+Ki*e(k)
*/

/**
 * @brief 增量式PI控制器
 * @param pMotorParam 电机参数结构体指针
 * @return void
 */
static void Incremental_PI(MotorParam_t *pMotorParam)
{

    pMotorParam->Bias = pMotorParam->Target - pMotorParam->Velocity; // 计算偏差
    pMotorParam->Motor_PWM += pMotorParam->Velocity_KP * (pMotorParam->Bias - pMotorParam->Last_bias) + pMotorParam->Velocity_KI * pMotorParam->Bias;
    // 限制PWM的范围在-16700到16700之间
    if (pMotorParam->Motor_PWM > 16700)
        pMotorParam->Motor_PWM = 16700;
    if (pMotorParam->Motor_PWM < -16700)
        pMotorParam->Motor_PWM = -16700;
    pMotorParam->Last_bias = pMotorParam->Bias; // 保存上一次偏差

    // //清除PWM标志位，该位为1时代表需要清除PWM
    // if( start_clear )
    // {
    // 	//PWM逐渐递减的方式清除，减缓小车由于电机释放而造成轻微移动的影响
    // 	if(Pwm>0) Pwm--;
    // 	if(Pwm<0) Pwm++;

    // 	//若清除完毕，则标记标志位，4个电机分别用4个bit表示
    // 	if( Pwm<2.0f&&Pwm>-2.0f ) Pwm=0,clear_state |= 1<<0;
    // 	else clear_state &= ~(1<<0);
    // }
}

/**
 * @brief 速度PID控制，对四个电机进行速度控制
 * @param pMotor 电机结构体指针
 * @return void
 */
void VelocityPIDControl(Robot_t *pRobot)
{
    // 设置PID参数
    pRobot->MotorA.Velocity_KP = pRobot->MotorB.Velocity_KP = pRobot->MotorC.Velocity_KP = pRobot->MotorD.Velocity_KP = 800;
    pRobot->MotorA.Velocity_KI = pRobot->MotorB.Velocity_KI = pRobot->MotorC.Velocity_KI = pRobot->MotorD.Velocity_KI = 500.0f;
    Incremental_PI(&pRobot->MotorA);
    Incremental_PI(&pRobot->MotorB);
    Incremental_PI(&pRobot->MotorC);
    Incremental_PI(&pRobot->MotorD);
    Set_PWM(pRobot->MotorA.Motor_PWM, pRobot->MotorB.Motor_PWM, pRobot->MotorC.Motor_PWM, pRobot->MotorD.Motor_PWM);
}

// 运动学逆解，根据vx,vy,vz计算四个电机的目标速度
void InverseKinematic(Robot_t *pRobot)
{
    float amplitude = 1.0f; // 车轮目标速度限幅
    // 运动学逆解，根据vx,vy,vz计算四个电机的目标速度
    // Inverse kinematics //运动学逆解
    pRobot->MotorA.Target = pRobot->MoveSpeed.X_Speed - pRobot->MoveSpeed.Z_Speed * (WHEEL_SPACING + AXLE_SPACING) / 2.0f; // 计算出左轮的目标速度
    pRobot->MotorB.Target = pRobot->MoveSpeed.X_Speed - pRobot->MoveSpeed.Z_Speed * (WHEEL_SPACING + AXLE_SPACING) / 2.0f; // 计算出左轮的目标速度
    pRobot->MotorC.Target = pRobot->MoveSpeed.X_Speed + pRobot->MoveSpeed.Z_Speed * (WHEEL_SPACING + AXLE_SPACING) / 2.0f; // 计算出右轮的目标速度
    pRobot->MotorD.Target = pRobot->MoveSpeed.X_Speed + pRobot->MoveSpeed.Z_Speed * (WHEEL_SPACING + AXLE_SPACING) / 2.0f; // 计算出右轮的目标速度

    // Wheel (motor) target speed limit //车轮(电机)目标速度限幅
    pRobot->MotorA.Target = target_limit_float(pRobot->MotorA.Target, -amplitude, amplitude);
    pRobot->MotorB.Target = target_limit_float(pRobot->MotorB.Target, -amplitude, amplitude);
    pRobot->MotorC.Target = target_limit_float(pRobot->MotorC.Target, -amplitude, amplitude);
    pRobot->MotorD.Target = target_limit_float(pRobot->MotorD.Target, -amplitude, amplitude);

    // pRobot->MotorA.Target *= LeftWheelDiff;
    // pRobot->MotorB.Target *= LeftWheelDiff;
    // pRobot->MotorC.Target *= RightWheelDiff;
    // pRobot->MotorD.Target *= RightWheelDiff;
}

float target_limit_float(float insert, float low, float high)
{
    if (insert < low)
        return low;
    else if (insert > high)
        return high;
    else
        return insert;
}

/**************************************************************************
Function: Handle PS2 controller control commands
Input   : none
Output  : none
函数功能：对PS2手柄控制命令进行处理
入口参数：无
返回  值：无
**************************************************************************/
#include "xbox360_gamepad.h"
#include "WiredPS2_gamepad.h"
// xbox360游戏手柄按键回调函数
void Xbox360GamePad_KeyEvent_Callback(uint8_t keyid, GamePadKeyEventType_t event)
{
    // 按下start按键
    if (keyid == Xbox360KEY_Menu && event == GamePadKeyEvent_SINGLECLICK)
        GamePadInterface->StartFlag = 1;

    if (gamepad_brand == Xbox360)
    {
        // 手柄加减速
        if (keyid == Xbox360KEY_LB && (event == GamePadKeyEvent_DOUBLECLICK || event == GamePadKeyEvent_SINGLECLICK))
            RC_Velocity -= 50;
        else if (keyid == Xbox360KEY_RB && (event == GamePadKeyEvent_DOUBLECLICK || event == GamePadKeyEvent_SINGLECLICK))
            RC_Velocity += 50;

        if (RC_Velocity < 0)
            RC_Velocity = 0;
    }
    else if (gamepad_brand == PS2_USB_Wiredless)
    {
        if (keyid == Xbox360KEY_LB && (event == GamePadKeyEvent_DOUBLECLICK || event == GamePadKeyEvent_SINGLECLICK))
            RC_Velocity += 50;
        else if (keyid == Xbox360_PaddingBit && (event == GamePadKeyEvent_DOUBLECLICK || event == GamePadKeyEvent_SINGLECLICK))
            RC_Velocity -= 50;
        if (RC_Velocity < 0)
            RC_Velocity = 0;
    }

    // 震动激活与取消
    if (keyid == Xbox360KEY_SELECT && event == GamePadKeyEvent_LONGCLICK)
    {
        if (GamePadInterface->Vib_EN)
        {
            GamePadInterface->SetVibration(0, 127);
            vTaskDelay(50);
            GamePadInterface->Vib_EN = !GamePadInterface->Vib_EN;
        }
        else
        {
            GamePadInterface->Vib_EN = !GamePadInterface->Vib_EN;
            vTaskDelay(50);
            GamePadInterface->SetVibration(0, 127);
        }
    }
}

// 有线USB手柄回调函数
void Wired_USB_PS2GamePad_KeyEvent_Callback(uint8_t keyid, GamePadKeyEventType_t event)
{
    // 按下start按键
    if (keyid == PS2KEY_START && event == GamePadKeyEvent_SINGLECLICK)
        GamePadInterface->StartFlag = 1;

    // 手柄加减速
    else if (keyid == PS2KEY_L2 && (event == GamePadKeyEvent_DOUBLECLICK || event == GamePadKeyEvent_SINGLECLICK))
        RC_Velocity -= 50;
    else if (keyid == PS2KEY_L1 && (event == GamePadKeyEvent_DOUBLECLICK || event == GamePadKeyEvent_SINGLECLICK))
        RC_Velocity += 50;

    if (RC_Velocity < 0)
        RC_Velocity = 0;
}

// 经典PS2手柄回调函数,非USB款
void Classic_PS2GamePad_KeyEvent_Callback(uint8_t keyid, GamePadKeyEventType_t event)
{
    // 按下start按键
    if (keyid == PS2KEY_START && event == GamePadKeyEvent_SINGLECLICK)
        GamePadInterface->StartFlag = 1;

    // 手柄加减速
    else if (keyid == PS2KEY_L2 && (event == GamePadKeyEvent_DOUBLECLICK || event == GamePadKeyEvent_SINGLECLICK))
        RC_Velocity -= 50;
    else if (keyid == PS2KEY_L1 && (event == GamePadKeyEvent_DOUBLECLICK || event == GamePadKeyEvent_SINGLECLICK))
        RC_Velocity += 50;

    if (RC_Velocity < 0)
        RC_Velocity = 0;
}

// 手柄震动映射函数
static uint8_t map_to_vib(float x)
{
    // 检查输入范围，限制在 [0.2, 1.2] 内
    if (x < 0.1f)
        return 0;
    if (x > 1.2f)
        x = 1.2f;

    // 线性映射
    float result = 255.0f * (x - 0.1f) / 1.1f;

    // 四舍五入并转换为 uint8_t
    return (uint8_t)(result + 0.5f);
}

void PS2_control(Robot_t *pRobot, IMU_DATA_t *pIMUData)
{
    float LX = 127, LY = 127, RX = 127;
    float ThrottleTri = 255;

    // 前进摇杆
    LY = GamePadInterface->LY - 127;

    // 左右横移
    LX = 127 - GamePadInterface->LX;

    // 顺逆时针
    RX = 127 - GamePadInterface->RX;

    // 摇杆微小幅度过滤
    if (fabs(LY) < 20)
        LY = 0;
    if (fabs(LX) < 20)
        LX = 0;
    if (fabs(RX) < 20)
        RX = 0;

    // 针对xbox360手柄，扳机为模拟量时，允许使用扳机控制
    if (gamepad_brand == Xbox360)
    {
        // 前进摇杆无值时,采用扳机的值
        if ((int)LY == 0)
        {
            if (GamePadInterface->LT == 0 && GamePadInterface->RT != 0)
                ThrottleTri = GamePadInterface->RT, LY = 127;
            else if (GamePadInterface->LT != 0 && GamePadInterface->RT == 0)
                ThrottleTri = -GamePadInterface->LT, LY = 127;
            else
                ThrottleTri = 0;
        }
    }

    // 针对usb有线手柄,在非模拟量模式下的摇杆值映射
    else if (gamepad_brand == PS2_USB_Wired || gamepad_brand == PS2_USB_WiredV2)
    {
        if (fabs(RX) < 0.0001f)
        {
            if (GamePadInterface->getKeyState(PS2KEY_4PINK))
                RX = 127;
            else if (GamePadInterface->getKeyState(PS2KEY_2RED))
                RX = -127;
        }
    }

    // Handle PS2 controller control commands
    // 对PS2手柄控制命令进行处理

    pRobot->MoveSpeed.X_Speed = (LY / 127.0f) * RC_Velocity * (ThrottleTri / 255.0f);
    pRobot->MoveSpeed.Y_Speed = (LX / 127.0f) * RC_Velocity;
    pRobot->MoveSpeed.Z_Speed = (PI / 2) * (RX / 127.0f) * (RC_Velocity / 500.0f);

    //		Move_X=LX*RC_Velocity/128;
    //		Move_Y=LY*RC_Velocity/128;
    //		Move_Z=RY*(PI/2)/128;

    // Z-axis data conversion //Z轴数据转化
    // if (Car_Mode == Mec_Car || Car_Mode == Omni_Car || Car_Mode == Mec_Car_V550)
    // {
    //     Move_Z = Move_Z * RC_Velocity / 500;
    // }
    // else if (Car_Mode == Akm_Car)
    // {
    //     // Ackermann structure car is converted to the front wheel steering Angle system target value, and kinematics analysis is pearformed
    //     // 阿克曼结构小车转换为前轮转向角度
    //     Move_Z = Move_Z * 2 / 9;
    // }
    // else if (Car_Mode == Diff_Car || Car_Mode == Tank_Car || Car_Mode == FourWheel_Car || Car_Mode == FourWheel_Car_V550)
    // {
    if (pRobot->MoveSpeed.X_Speed < 0)
        pRobot->MoveSpeed.Z_Speed = -pRobot->MoveSpeed.Z_Speed; // The differential control principle series requires this treatment //差速控制原理系列需要此处理
    pRobot->MoveSpeed.Z_Speed = pRobot->MoveSpeed.Z_Speed * RC_Velocity / 500;
    // }

    // Unit conversion, mm/s -> m/s
    // 单位转换，mm/s -> m/s
    pRobot->MoveSpeed.X_Speed = pRobot->MoveSpeed.X_Speed / 1000;
    pRobot->MoveSpeed.Y_Speed = pRobot->MoveSpeed.Y_Speed / 1000;
    pRobot->MoveSpeed.Z_Speed = pRobot->MoveSpeed.Z_Speed;

    

    // Control target value is obtained and kinematics analysis is performed
    // 得到控制目标值，进行运动学分析
    InverseKinematic(pRobot);
    VelocityPIDControl(pRobot);

// 根据加速度反应震动情况传达到手柄
#include "bsp_gamepad.h"

    // Z轴数据判断震动强度
    float now_z = pIMUData->accel.z / 1671.84f;
    static float last_z = 0;
    float strength = fabs(last_z - now_z);

    // 震动映射到手柄
    if (strength > 0.1f && SysVal.Time_count > CONTROL_DELAY)
    {
        if (GamePadInterface->SetVibration != NULL)
            GamePadInterface->SetVibration(map_to_vib(strength), 0);
    }
    last_z = now_z;
}
