import os

from PIL import Image

from jmcomic import *
from jmcomic.cli import JmcomicUI

# 下方填入你要下载的本子的id，一行一个，每行的首尾可以有空白字符
jm_albums = '''



'''

# 单独下载章节
jm_photos = '''



'''


def env(name, default, trim=('[]', '""', "''")):
    import os
    value = os.getenv(name, None)
    if value is None or value == '':
        return default

    for pair in trim:
        if value.startswith(pair[0]) and value.endswith(pair[1]):
            value = value[1:-1]

    return value


def get_id_set(env_name, given):
    aid_set = set()
    for text in [
        given,
        (env(env_name, '')).replace('-', '\n'),
    ]:
        aid_set.update(str_to_set(text))

    return aid_set


def compress_image_in_place(filepath, quality, convert_to_jpeg=False):
    target_path = filepath
    temp_path = f'{filepath}.jmcomic-compress.tmp'
    original_size = os.path.getsize(filepath)

    try:
        with Image.open(filepath) as image:
            image_format = image.format
            image_info = image.info.copy()
            save_kwargs = {}

            if convert_to_jpeg and image_format in {'PNG', 'WEBP'}:
                image_format = 'JPEG'
                target_path = os.path.splitext(filepath)[0] + '.jpg'
                if image.mode not in {'RGB', 'L'}:
                    if image.mode in {'RGBA', 'LA'} or 'transparency' in image_info:
                        image = image.convert('RGBA')
                        background = Image.new('RGB', image.size, 'white')
                        background.paste(image, mask=image.getchannel('A'))
                        image = background
                    else:
                        image = image.convert('RGB')
                save_kwargs.update(quality=quality, optimize=True)
            elif image_format in {'JPEG', 'JPG'}:
                save_kwargs.update(quality=quality, optimize=True)
            elif image_format == 'WEBP':
                save_kwargs.update(quality=quality)
            elif image_format == 'PNG':
                return image_format, None, None, False, filepath
            else:
                return image_format, None, None, False, filepath

            for key in ('exif', 'icc_profile'):
                value = image_info.get(key)
                if value is not None:
                    save_kwargs[key] = value

            image.save(temp_path, format=image_format, **save_kwargs)

        compressed_size = os.path.getsize(temp_path)
        if target_path == filepath and compressed_size >= original_size:
            os.remove(temp_path)
            return image_format, original_size, compressed_size, False, filepath

        os.replace(temp_path, target_path)
        if target_path != filepath:
            os.remove(filepath)

        return image_format, original_size, compressed_size, True, target_path
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


class WorkflowImageCompressPlugin(JmOptionPlugin):
    plugin_key = 'workflow_image_compress'

    def invoke(self, image, quality, convert_to_jpeg=False, **kwargs):
        old_path = image.save_path
        image_format, original_size, compressed_size, replaced, new_path = compress_image_in_place(
            old_path,
            quality,
            convert_to_jpeg,
        )

        if original_size is None:
            self.log(f'跳过不支持质量压缩的图片格式: {image_format}, {old_path}')
            return

        if new_path != old_path:
            image.save_path = new_path

        action = '压缩完成' if replaced else '压缩后未变小，保留原图'
        self.log(
            f'{action}: {new_path}, '
            f'{original_size / 1024:.1f}KB → {compressed_size / 1024:.1f}KB'
        )


def main():
    album_id_set = get_id_set('JM_ALBUM_IDS', jm_albums)
    photo_id_set = get_id_set('JM_PHOTO_IDS', jm_photos)

    helper = JmcomicUI()
    helper.album_id_list = list(album_id_set)
    helper.photo_id_list = list(photo_id_set)

    option = get_option()
    helper.run(option)
    option.call_all_plugin('after_download')


def get_option():
    # 读取 option 配置文件
    option = create_option(os.path.abspath(os.path.join(__file__, '../../assets/option/option_workflow_download.yml')))

    # 支持工作流覆盖配置文件的配置
    cover_option_config(option)

    # 把请求错误的html下载到文件，方便GitHub Actions下载查看日志
    log_before_raise()

    return option


def cover_option_config(option: JmOption):
    dir_rule = env('DIR_RULE', None)
    if dir_rule is not None:
        the_old = option.dir_rule
        the_new = DirRule(dir_rule, base_dir=the_old.base_dir)
        option.dir_rule = the_new

    impl = env('CLIENT_IMPL', None)
    if impl is not None:
        option.client.impl = impl

    suffix = env('IMAGE_SUFFIX', None)
    if suffix is not None:
        option.download.image.suffix = fix_suffix(suffix)

    pdf_option = env('PDF_OPTION', None)
    convert_to_jpeg = bool(pdf_option and pdf_option != '否')

    try:
        image_quality = int(env('IMAGE_QUALITY', '100'))
    except ValueError:
        ExceptionTool.raises('IMAGE_QUALITY 必须是1到100之间的整数')

    ExceptionTool.require_true(
        1 <= image_quality <= 100,
        'IMAGE_QUALITY 必须是1到100之间的整数'
    )

    if image_quality < 100:
        JmModuleConfig.register_plugin(WorkflowImageCompressPlugin)
        option.plugins.setdefault('after_image', []).append({
            'plugin': WorkflowImageCompressPlugin.plugin_key,
            'kwargs': {
                'quality': image_quality,
                'convert_to_jpeg': convert_to_jpeg,
            },
        })

    if pdf_option and pdf_option != '否':
        call_when = 'after_album' if pdf_option == '是 | 本子维度合并pdf' else 'after_photo'
        
        pdf_name_rule = env('PDF_NAME_RULE', None)
        if isinstance(pdf_name_rule, str):
            pdf_name_rule = pdf_name_rule.strip()
            
        if not pdf_name_rule:
            pdf_name_rule = '[JM{Aid}] {Atitle}' if call_when == 'after_album' else '[JM{Aid}] 第{Pindex}章-JM{Pid}-{Ptitle}'
            
        plugin = [{
            'plugin': Img2pdfPlugin.plugin_key,
            'kwargs': {
                'pdf_dir': option.dir_rule.base_dir + '/pdf/',
                'filename_rule': pdf_name_rule,
                'delete_original_file': True,
            }
        }]
        option.plugins[call_when] = plugin


def log_before_raise():
    jm_download_dir = env('JM_DOWNLOAD_DIR', workspace())
    mkdir_if_not_exists(jm_download_dir)

    def decide_filepath(e):
        resp = e.context.get(ExceptionTool.CONTEXT_KEY_RESP, None)

        if resp is None:
            suffix = str(time_stamp())
        else:
            suffix = resp.url

        name = '-'.join(
            fix_windir_name(it)
            for it in [
                e.description,
                current_thread().name,
                suffix
            ]
        )

        path = f'{jm_download_dir}/【出错了】{name}.log'
        return path

    def exception_listener(e: JmcomicException):
        """
        异常监听器，实现了在 GitHub Actions 下，把请求错误的信息下载到文件，方便调试和通知使用者
        """
        # 决定要写入的文件路径
        path = decide_filepath(e)

        # 准备内容
        content = [
            str(type(e)),
            e.msg,
        ]
        for k, v in e.context.items():
            content.append(f'{k}: {v}')

        # resp.text
        resp = e.context.get(ExceptionTool.CONTEXT_KEY_RESP, None)
        if resp:
            content.append(f'响应文本: {resp.text}')

        # 写文件
        write_text(path, '\n'.join(content))

    JmModuleConfig.register_exception_listener(JmcomicException, exception_listener)


if __name__ == '__main__':
    main()
