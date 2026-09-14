#include <opencv2/opencv.hpp>
#include <opencv2/geometry.hpp> // OpenCV 5: getRotationMatrix2D 已移入 geometry 模块
#include <iostream>

int main()
{
    // 创建画布
    cv::Mat canvas = cv::Mat::zeros(600, 800, CV_8UC3);
    canvas.setTo(cv::Scalar(255, 255, 255));

    // 1. 基础文字绘制
    // putText(图像, 文字, 位置, 字体, 缩放, 颜色, 线宽, 线型)
    cv::putText(canvas, "Hello OpenCV!", cv::Point(50, 50),
                cv::FONT_HERSHEY_SIMPLEX, 1.0,
                cv::Scalar(0, 0, 0), 2, cv::LINE_AA);

    // 2. 不同字体样式
    // 可用字体: HERSHEY_SIMPLEX, HERSHEY_PLAIN, HERSHEY_DUPLEX,
    //          HERSHEY_COMPLEX, HERSHEY_TRIPLEX, HERSHEY_SCRIPT_SIMPLEX 等

    int y_offset = 100;
    std::string fonts[] = {
        "SIMPLEX", "PLAIN", "DUPLEX", "COMPLEX",
        "TRIPLEX", "SCRIPT_SIMPLEX", "SCRIPT_COMPLEX"};
    int font_types[] = {
        cv::FONT_HERSHEY_SIMPLEX, cv::FONT_HERSHEY_PLAIN,
        cv::FONT_HERSHEY_DUPLEX, cv::FONT_HERSHEY_COMPLEX,
        cv::FONT_HERSHEY_TRIPLEX, cv::FONT_HERSHEY_SCRIPT_SIMPLEX,
        cv::FONT_HERSHEY_SCRIPT_COMPLEX};

    for (int i = 0; i < 7; i++)
    {
        cv::putText(canvas, fonts[i] + " Style",
                    cv::Point(50, y_offset + i * 50),
                    font_types[i], 0.8,
                    cv::Scalar(0, 100, 200), 1, cv::LINE_AA);
    }

    // 3. 不同大小和颜色的文字
    cv::putText(canvas, "Large Red Text", cv::Point(450, 150),
                cv::FONT_HERSHEY_SIMPLEX, 2.0,
                cv::Scalar(0, 0, 255), 3, cv::LINE_AA);

    cv::putText(canvas, "Small Green Text", cv::Point(450, 250),
                cv::FONT_HERSHEY_SIMPLEX, 0.6,
                cv::Scalar(0, 255, 0), 1, cv::LINE_AA);

    // 4. 绘制旋转文字（通过仿射变换）
    std::string text = "Rotated Text";
    double angle = -45.0;
    int base_line;
    cv::Size text_size = cv::getTextSize(text, cv::FONT_HERSHEY_SIMPLEX,
                                         1.5, 2, &base_line);

    // 创建临时图像绘制文字
    cv::Mat text_img = cv::Mat::zeros(text_size.height + base_line + 20,
                                      text_size.width + 20, CV_8UC3);
    text_img.setTo(cv::Scalar(255, 255, 255));
    cv::putText(text_img, text, cv::Point(10, text_size.height),
                cv::FONT_HERSHEY_SIMPLEX, 1.5,
                cv::Scalar(255, 0, 0), 2, cv::LINE_AA);

    // 旋转矩阵
    cv::Point2f center(text_img.cols / 2.0f, text_img.rows / 2.0f);
    cv::Mat rot_mat = cv::getRotationMatrix2D(center, angle, 1.0);

    cv::Mat rotated_text;
    cv::warpAffine(text_img, rotated_text, rot_mat, text_img.size());

    // 将旋转后的文字贴到主画布
    cv::Rect roi(450, 300, rotated_text.cols, rotated_text.rows);
    rotated_text.copyTo(canvas(roi));

    // 5. 绘制中文（需要额外支持，这里展示英文）
    cv::putText(canvas, "Score: 95.5", cv::Point(50, 550),
                cv::FONT_HERSHEY_SIMPLEX, 1.2,
                cv::Scalar(128, 128, 0), 2, cv::LINE_AA);

    cv::imshow("Text Demo", canvas);
    cv::waitKey(0);

    return 0;
}
