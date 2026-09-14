#include <opencv2/opencv.hpp>
#include <opencv2/geometry.hpp> // OpenCV 5: getRotationMatrix2D 已移入 geometry 模块
#include <iostream>
#include <cmath>

int main()
{
    cv::Mat image = cv::imread("lena.jpg");
    if (image.empty())
    {
        image = cv::Mat(400, 400, CV_8UC3, cv::Scalar(220, 220, 220));
        cv::rectangle(image, cv::Point(150, 150), cv::Point(250, 250),
                      cv::Scalar(0, 0, 255), -1);
        cv::circle(image, cv::Point(200, 200), 30, cv::Scalar(0, 255, 0), -1);
    }

    double angle = 45.0; // 旋转角度
    double scale = 1.0;  // 缩放因子

    // 获取旋转中心
    cv::Point2f center(image.cols / 2.0f, image.rows / 2.0f);

    // 方法1: 使用 getRotationMatrix2D 获取旋转矩阵（2x3矩阵）
    cv::Mat rot_mat = cv::getRotationMatrix2D(center, angle, scale);

    // 计算旋转后图像的边界框（防止裁剪）
    // 旋转矩阵元素
    double cos_angle = std::abs(rot_mat.at<double>(0, 0));
    double sin_angle = std::abs(rot_mat.at<double>(0, 1));

    int new_width = static_cast<int>(image.rows * sin_angle + image.cols * cos_angle);
    int new_height = static_cast<int>(image.rows * cos_angle + image.cols * sin_angle);

    // 调整旋转矩阵的平移部分，使图像居中
    rot_mat.at<double>(0, 2) += (new_width - image.cols) / 2.0;
    rot_mat.at<double>(1, 2) += (new_height - image.rows) / 2.0;

    // 执行仿射变换
    cv::Mat rotated;
    cv::warpAffine(image, rotated, rot_mat, cv::Size(new_width, new_height),
                   cv::INTER_LINEAR, cv::BORDER_CONSTANT, cv::Scalar(255, 255, 255));

    // 方法2: 简单旋转（不调整边界，会裁剪）
    cv::Mat rotated_crop;
    cv::warpAffine(image, rotated_crop,
                   cv::getRotationMatrix2D(center, angle, scale),
                   image.size());

    // 方法3: 使用旋转矩形进行任意角度旋转（更灵活）
    cv::Mat rotated_any;
    cv::RotatedRect rRect(center, image.size(), angle);
    cv::Mat rMat = cv::getRotationMatrix2D(rRect.center, angle, scale);
    cv::warpAffine(image, rotated_any, rMat, rRect.boundingRect().size());

    // 显示
    cv::imshow("Original", image);
    cv::imshow("Rotated (Full)", rotated);
    cv::imshow("Rotated (Crop)", rotated_crop);

    // 连续旋转演示
    cv::Mat continuous = image.clone();
    for (int a = 0; a < 360; a += 30)
    {
        cv::Mat r;
        cv::Point2f c(continuous.cols / 2.0f, continuous.rows / 2.0f);
        cv::Mat m = cv::getRotationMatrix2D(c, a, 1.0);
        cv::warpAffine(continuous, r, m, continuous.size(),
                       cv::INTER_LINEAR, cv::BORDER_WRAP);
        cv::imshow("Animation", r);
        cv::waitKey(100);
    }

    cv::waitKey(0);
    return 0;
}
