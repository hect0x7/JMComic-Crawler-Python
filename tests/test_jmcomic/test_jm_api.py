from test_jmcomic import *


def download_image(image_url: str) -> bytes:
    """
    下载图片并返回字节内容。
    
    :param image_url: 图片URL
    :return: 图片的字节流
    """
    import requests
    
    response = requests.get(image_url, stream=True)
    response.raise_for_status()
    return response.content

class Test_Api(JmTestConfigurable):
    def test_fetch_and_decrypt_images(jm_id: int = 438516, output_dir: str = "output_dir"):
        """
        测试下载并解密图片
        :param jm_album_id: 本子的禁漫车号
        :param output_dir: 输出目录
        """
        import os

        # 确保输出目录存在
        os.makedirs(output_dir, exist_ok=True)
        # 获取专辑详情和图片数据列表
        album, image_data_list = get_album_images(jm_id)
        print(f"调试信息: {album}, {image_data_list}")
        
        for image_data in image_data_list:
            print(f"正在处理: {image_data.image.img_file_name},调试信息:{image_data}")
            image_url = image_data.image.img_url
            image_num = image_data.image_num
            
            # 下载图片内容
            image_content = download_image(image_url)
            
            # 解密图片
            restored_content = restore_original_image(image_num, image_content)
            
            # 生成文件名并保存
            file_path = os.path.join(output_dir, f"{image_data.image.img_file_name}.jpg")
            with open(file_path, "wb") as f:
                f.write(restored_content)
            print(f"已保存: {file_path}")

    def test_download_photo_by_id(self):
        """
        测试jmcomic模块的api的使用
        """
        photo_id = "438516"
        jmcomic.download_photo(photo_id, self.option)

    def test_download_album_by_id(self):
        """
        测试jmcomic模块的api的使用
        """
        album_id = '438516'
        jmcomic.download_album(album_id, self.option)

    def test_batch(self):
        album_ls = str_to_list('''
        326361
        366867
        438516
        ''')

        test_cases: Iterable = [
            {e: None for e in album_ls}.keys(),
            {i: e for i, e in enumerate(album_ls)}.values(),
            set(album_ls),
            tuple(album_ls),
            album_ls,
        ]

        for case in test_cases:
            ret1 = jmcomic.download_album(case, self.option)
            self.assertEqual(len(ret1), len(album_ls), str(case))

            ret2 = jmcomic.download_album(case, self.option)
            self.assertEqual(len(ret2), len(album_ls), str(case))

        # 测试 Generator
        ret2 = jmcomic.download_album((e for e in album_ls), self.option)
        self.assertEqual(len(ret2), len(album_ls), 'Generator')

    def test_get_jmcomic_domain(self):
        func_list = {
            self.client.get_html_domain,
            self.client.get_html_domain_all,
            self.client.get_html_domain_all_via_github,
            # JmModuleConfig.get_jmcomic_url,
            # JmModuleConfig.get_jmcomic_domain_all,
        }

        exception_list = []

        def run_func_async(func):
            try:
                print(func())
            except BaseException as e:
                exception_list.append(e)
                traceback_print_exec()

        multi_thread_launcher(
            iter_objs=func_list,
            apply_each_obj_func=run_func_async,
        )

        if len(exception_list) == 0:
            return

        if self.client.is_given_type(JmApiClient):
            return

        for e in exception_list:
            print(e)

        raise AssertionError(exception_list)
