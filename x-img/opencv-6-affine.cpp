#include <opencv2/opencv.hpp>
#include <opencv2/geometry.hpp> // OpenCV 5: getAffineTransform/getPerspectiveTransform 已移入 geometry 模块
#include <iostream>
#include <vector>

int main()
{
    cv::Mat image = cv::imread("lena.jpg");
    if (image.empty())
    {
        image = cv::Mat(400, 400, CV_8UC3, cv::Scalar(200, 200, 200));
        // 绘制棋盘格用于观察变形
        for (int i = 0; i < 400; i += 50)
        {
            cv::line(image, cv::Point(i, 0), cv::Point(i, 400),
                     cv::Scalar(0, 0, 0), 1);
            cv::line(image, cv::Point(0, i), cv::Point(400, i),
                     cv::Scalar(0, 0, 0), 1);
        }
        cv::rectangle(image, cv::Point(100, 100), cv::Point(300, 300),
                      cv::Scalar(0, 0, 255), 2);
    }

    // ===== 1. 平移变换 =====
    cv::Mat trans_mat = (cv::Mat_<double>(2, 3) << 1, 0, 50, // x方向平移50
                         0, 1, 100                           // y方向平移100
    );
    cv::Mat translated;
    cv::warpAffine(image, translated, trans_mat, image.size());

    // ===== 2. 缩放变换 =====
    double scale_x = 0.5, scale_y = 0.5;
    cv::Mat scale_mat = (cv::Mat_<double>(2, 3) << scale_x, 0, 0,
                         0, scale_y, 0);
    cv::Mat scaled;
    cv::warpAffine(image, scaled, scale_mat,
                   cv::Size(image.cols * scale_x, image.rows * scale_y));

    // ===== 3. 剪切变换（Shear） =====
    double shear_x = 0.3;
    cv::Mat shear_mat = (cv::Mat_<double>(2, 3) << 1, shear_x, 0,
                         0, 1, 0);
    cv::Mat sheared;
    cv::warpAffine(image, sheared, shear_mat, image.size());

    // ===== 4. 三点定义的仿射变换（最常用） =====
    // 原始三个点
    cv::Point2f src_pts[3] = {
        cv::Point2f(0, 0),              // 左上
        cv::Point2f(image.cols - 1, 0), // 右上
        cv::Point2f(0, image.rows - 1)  // 左下
    };

    // 目标三个点（形成透视效果）
    cv::Point2f dst_pts[3] = {
        cv::Point2f(50, 50),               // 左上内移
        cv::Point2f(image.cols - 50, 100), // 右上内移且下移
        cv::Point2f(20, image.rows - 20)   // 左下内移
    };

    cv::Mat affine_mat = cv::getAffineTransform(src_pts, dst_pts);
    cv::Mat warped;
    cv::warpAffine(image, warped, affine_mat, image.size());

    // ===== 5. 透视变换（需要4个点，使用3x3矩阵） =====
    cv::Point2f src_persp[4] = {
        cv::Point2f(100, 100),
        cv::Point2f(300, 100),
        cv::Point2f(300, 300),
        cv::Point2f(100, 300)};
    cv::Point2f dst_persp[4] = {
        cv::Point2f(100, 100),
        cv::Point2f(300, 80),  // 上边缘变窄
        cv::Point2f(300, 320), // 下边缘变宽
        cv::Point2f(100, 300)};

    cv::Mat persp_mat = cv::getPerspectiveTransform(src_persp, dst_persp);
    cv::Mat perspective;
    cv::warpPerspective(image, perspective, persp_mat, image.size());

    // ===== 6. 图像拼接：使用仿射变换对齐 =====
    // 创建两个有重叠的图像
    cv::Mat img1 = image(cv::Rect(0, 0, 300, 400)).clone();
    cv::Mat img2 = image(cv::Rect(200, 0, 200, 400)).clone();

    // 将img2平移到img1的坐标系
    cv::Mat align_mat = (cv::Mat_<double>(2, 3) << 1, 0, -200, // 向左平移200
                         0, 1, 0);
    cv::Mat aligned;
    cv::warpAffine(img2, aligned, align_mat, img1.size());

    // 融合
    cv::Mat blended;
    cv::addWeighted(img1, 0.5, aligned, 0.5, 0, blended);

    // 显示所有结果
    cv::imshow("Original", image);
    cv::imshow("1. Translated", translated);
    cv::imshow("2. Scaled", scaled);
    cv::imshow("3. Sheared", sheared);
    cv::imshow("4. Affine (3-point)", warped);
    cv::imshow("5. Perspective (4-point)", perspective);
    cv::imshow("6. Alignment Demo", blended);

    // 打印变换矩阵
    std::cout << "Translation Matrix:\n"
              << trans_mat << "\n\n";
    std::cout << "Affine Matrix (3-point):\n"
              << affine_mat << "\n\n";
    std::cout << "Perspective Matrix:\n"
              << persp_mat << std::endl;

    cv::waitKey(0);
    return 0;
}
