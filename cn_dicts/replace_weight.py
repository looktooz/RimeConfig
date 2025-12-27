import sys
import os
import datetime
import re

def detect_column_types(data_lines):
    """
    根据每行的内容特征识别每行的列类型
    返回一个字典，键为列索引，值为列类型（"phrase", "code", "weight"）
    采用逐行分析，统计每列出现类型的频率，选择频率最高的类型
    """
    if not data_lines:
        return {}

    # 统计每列的特征 - 记录每列每种类型出现的次数
    column_stats = {}

    # 收集所有非空行的数据
    for _, line_content, _ in data_lines:
        if not line_content.strip():
            continue

        parts = line_content.split('\t')

        # 识别该行每个单元格的类型
        cell_types = []
        for cell in parts:
            cell = cell.strip()
            if not cell:
                cell_types.append("unknown")
                continue

            # 1. 检查是否为权重（整数）
            if re.fullmatch(r'-?\d+', cell):
                cell_types.append("weight")
            # 2. 检查是否为编码/拼音（全小写字母）
            elif re.fullmatch(r'[a-z]+', cell):
                cell_types.append("code")
            # 3. 其他情况都认为是词组
            else:
                cell_types.append("phrase")

        # 为每列统计特征
        for i, cell_type in enumerate(cell_types):
            if i not in column_stats:
                column_stats[i] = {
                    'total': 0,
                    'phrase': 0,
                    'code': 0,
                    'weight': 0,
                    'unknown': 0
                }

            column_stats[i]['total'] += 1
            column_stats[i][cell_type] += 1

    # 根据统计结果确定每列的类型
    column_types = {}

    for col_idx, stats in column_stats.items():
        total = stats['total']
        if total == 0:
            continue

        # 找到出现次数最多的类型
        max_type = None
        max_count = -1

        for type_key in ['phrase', 'code', 'weight']:
            if stats[type_key] > max_count:
                max_count = stats[type_key]
                max_type = type_key

        # 如果最高频率的类型占总数的50%以上，就确定为此类型
        if max_count / total >= 0.5:
            column_types[col_idx] = max_type
        else:
            # 频率不够高，无法确定类型
            column_types[col_idx] = "unknown"

    return column_types

def analyze_row_pattern(parts):
    """
    分析单行的列模式，返回每个列索引对应的类型
    """
    cell_types = {}
    for i, cell in enumerate(parts):
        cell = cell.strip()
        if not cell:
            cell_types[i] = "unknown"
            continue

        # 1. 检查是否为权重（整数）
        if re.fullmatch(r'-?\d+', cell):
            cell_types[i] = "weight"
        # 2. 检查是否为编码/拼音（全小写字母）
        elif re.fullmatch(r'[a-z]+', cell):
            cell_types[i] = "code"
        # 3. 其他情况都认为是词组
        else:
            cell_types[i] = "phrase"

    return cell_types

def validate_row_by_column_types(parts, column_types):
    """根据列类型验证行数据"""
    errors = []

    for col_idx, col_type in column_types.items():
        if col_idx >= len(parts):
            errors.append(f"列{col_idx}不存在")
            continue

        cell = parts[col_idx].strip()

        if not cell:
            errors.append(f"{col_type}列为空")
            continue

        if col_type == "weight":
            if not re.fullmatch(r'-?\d+', cell):
                errors.append(f"权重列不是整数: '{cell}'")

        elif col_type == "code":
            if not re.fullmatch(r'[a-z]+', cell):
                errors.append(f"编码/拼音列不是小写英文字母: '{cell}'")

        elif col_type == "phrase":
            # 根据新要求，词组只需要非空即可
            # 可以是汉字、字母、数字、标点的任意组合
            if not cell.strip():
                errors.append(f"词组列为空")

    return errors

def find_columns_by_type_for_row(parts, column_types):
    """
    根据列类型和行内容找到该行的词组列和权重列
    返回 (phrase_col, weight_col)
    如果找不到，返回 (None, None)
    """
    # 首先尝试使用统计得出的列类型
    phrase_col = None
    weight_col = None

    for col_idx, col_type in column_types.items():
        if col_idx < len(parts):
            if col_type == "phrase" and phrase_col is None:
                phrase_col = col_idx
            elif col_type == "weight" and weight_col is None:
                weight_col = col_idx

    # 如果统计类型找不到，尝试分析该行的模式
    if phrase_col is None or weight_col is None:
        row_pattern = analyze_row_pattern(parts)

        # 在行模式中寻找词组和权重
        for col_idx, cell_type in row_pattern.items():
            if cell_type == "phrase" and phrase_col is None:
                phrase_col = col_idx
            elif cell_type == "weight" and weight_col is None:
                weight_col = col_idx

    return phrase_col, weight_col

def load_file_with_column_detection(file_path):
    """加载文件并检测列类型"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        # 查找注释结束标记
        comment_lines = []
        data_lines = []
        found_marker = False

        for i, line in enumerate(lines):
            line_content = line.rstrip('\n')

            if not found_marker:
                comment_lines.append(line)
                if line_content.strip() == '...':
                    found_marker = True
            else:
                data_lines.append((i, line_content, line))

        # 如果没有找到'...'，则所有行都是数据行
        if not found_marker:
            comment_lines = []
            data_lines = [(i, lines[i].rstrip('\n'), lines[i]) for i in range(len(lines))]

        # 检测列类型（基于统计）
        column_types = detect_column_types(data_lines)

        print(f"列类型检测结果: {column_types}")

        # 构建词组到权重的映射
        phrase_to_weight = {}
        phrase_to_index = {}  # 词组到行索引的映射（用于记录）

        for line_num, line_content, _ in data_lines:
            if not line_content.strip():
                continue

            parts = line_content.split('\t')

            # 跳过没有足够列的行
            if len(parts) < 2:
                print(f"警告: 第{line_num+1}行列数不足，已跳过")
                continue

            # 验证行数据
            errors = validate_row_by_column_types(parts, column_types)
            if errors:
                print(f"警告: 第{line_num+1}行数据验证失败: {'; '.join(errors)}")
                # 继续尝试，可能只是列顺序问题

            # 查找该行的词组列和权重列
            phrase_col, weight_col = find_columns_by_type_for_row(parts, column_types)

            if phrase_col is None:
                print(f"警告: 第{line_num+1}行未找到词组列")
                # 尝试查找包含汉字的列作为词组列
                for col_idx, cell in enumerate(parts):
                    cell = cell.strip()
                    if cell and re.search(r'[\u4e00-\u9fff]', cell):
                        phrase_col = col_idx
                        break

            if weight_col is None:
                print(f"警告: 第{line_num+1}行未找到权重列")
                # 尝试查找纯数字的列作为权重列
                for col_idx, cell in enumerate(parts):
                    cell = cell.strip()
                    if cell and re.fullmatch(r'-?\d+', cell):
                        weight_col = col_idx
                        break

            if phrase_col is None or weight_col is None:
                print(f"警告: 第{line_num+1}行无法确定词组列或权重列，已跳过")
                continue

            phrase = parts[phrase_col].strip()
            weight = parts[weight_col].strip() if weight_col < len(parts) else ""

            # 验证词组和权重
            if not phrase:
                print(f"警告: 第{line_num+1}行词组列为空，已跳过")
                continue

            if not weight and weight != "0":  # 允许权重为0
                print(f"警告: 第{line_num+1}行权重列为空，已跳过")
                continue

            phrase_to_weight[phrase] = weight
            phrase_to_index[phrase] = line_num

        return comment_lines, data_lines, column_types, phrase_to_weight, phrase_to_index

    except Exception as e:
        print(f"加载文件时发生错误: {str(e)}")
        return [], [], {}, {}, {}

def create_update_record(record_dir, script_name, timestamp, target_file_name, updated_count,
                         not_found_count, error_count, direction, source_file_name,
                         modified_lines, backup_file, original_content):
    """创建更新记录文件"""
    try:
        # 确保记录目录存在
        if not os.path.exists(record_dir):
            os.makedirs(record_dir)

        # 记录文件名 - 使用Python文件名_log_时间戳
        record_file = os.path.join(record_dir, f"{script_name}_log_{timestamp}.txt")

        with open(record_file, 'w', encoding='utf-8') as f:
            f.write(f"# 权重更新日志 - {timestamp}\n")
            f.write("*" * 30 + "\n\n")

            # 第一部分：更新、变动内容的汇总
            f.write(f"## 文件: {target_file_name}\n")
            f.write("-" * 40 + "\n")
            f.write(f"替换行数: {updated_count}\n")
            f.write(f"未找到匹配词组: {not_found_count} 个\n")
            f.write(f"处理错误: {error_count} 行\n")
            f.write(f"替换方向: {direction}\n")
            if direction == "用拖入文件替换基础文件":
                f.write(f"源文件: {source_file_name}\n")
                f.write(f"目标文件: phrase_weight.txt\n")
            else:
                f.write(f"源文件: phrase_weight.txt\n")
                f.write(f"目标文件: {source_file_name}\n")
            f.write("\n" + "*" * 30 + "\n\n")

            # 第二部分：具体更新、变动文件中的哪些内容
            f.write("## 此处为替换了哪些内容？\n")
            f.write("-" * 40 + "\n")
            if modified_lines:
                f.write(f"共修改了 {len(modified_lines)} 行:\n\n")
                for line in modified_lines:
                    f.write(f"{line}\n")
            else:
                f.write("本次更新没有修改任何行。\n")
            f.write("\n" + "*" * 30 + "\n\n")

            # 第三部分：备份的原文件
            f.write("## 此处为对原文件的备份\n")
            f.write("-" * 40 + "\n")
            if backup_file:
                f.write(f"原文件备份路径: {backup_file}\n\n")
                f.write("原文件内容:\n")
                f.write("-" * 40 + "\n")
                f.write(original_content)
            else:
                f.write("未能创建原文件备份。\n")

        return record_file
    except Exception as e:
        print(f"创建更新记录时发生错误: {str(e)}")
        return None

def replace_weights_direction1(drag_in_file, base_file, record_dir):
    """方向1：用拖入文件替换基础文件中的权重"""
    print("\n正在执行替换方向1：用拖入文件替换基础文件中的权重")

    # 加载拖入文件
    drag_in_comment_lines, drag_in_data_lines, drag_in_column_types, drag_in_mapping, drag_in_indices = load_file_with_column_detection(drag_in_file)
    if not drag_in_mapping:
        print("错误: 拖入文件中没有有效数据，无法继续")
        return False

    print(f"拖入文件中词组数量: {len(drag_in_mapping)}")

    # 加载基础文件
    base_comment_lines, base_data_lines, base_column_types, base_mapping, base_indices = load_file_with_column_detection(base_file)
    if not base_data_lines:
        print("错误: 基础文件中没有数据行")
        return False

    # 处理数据行
    updated_lines = []
    updated_count = 0
    not_found_count = 0
    error_count = 0
    modified_lines = []

    for line_num, line_content, original_line in base_data_lines:
        # 跳过空行
        if not line_content.strip():
            updated_lines.append(original_line)
            continue

        # 检查分隔符
        if '\t' not in line_content:
            print(f"警告: 基础文件第{line_num+1}行未找到Tab分隔符，已跳过: {line_content}")
            updated_lines.append(original_line)
            error_count += 1
            continue

        # 分割行
        parts = line_content.split('\t')

        # 跳过没有足够列的行
        if len(parts) < 2:
            print(f"警告: 基础文件第{line_num+1}行列数不足，已跳过")
            updated_lines.append(original_line)
            error_count += 1
            continue

        # 验证行数据
        errors = validate_row_by_column_types(parts, base_column_types)
        if errors:
            print(f"警告: 基础文件第{line_num+1}行数据验证失败: {'; '.join(errors)}")
            # 继续尝试，可能只是列顺序问题

        # 查找该行的词组列和权重列
        phrase_col, weight_col = find_columns_by_type_for_row(parts, base_column_types)

        if phrase_col is None:
            # 尝试查找包含汉字的列作为词组列
            for col_idx, cell in enumerate(parts):
                cell = cell.strip()
                if cell and re.search(r'[\u4e00-\u9fff]', cell):
                    phrase_col = col_idx
                    break

        if weight_col is None:
            # 尝试查找纯数字的列作为权重列
            for col_idx, cell in enumerate(parts):
                cell = cell.strip()
                if cell and re.fullmatch(r'-?\d+', cell):
                    weight_col = col_idx
                    break

        if phrase_col is None:
            print(f"警告: 基础文件第{line_num+1}行词组列不存在，已跳过")
            updated_lines.append(original_line)
            error_count += 1
            continue

        if weight_col is None:
            print(f"警告: 基础文件第{line_num+1}行权重列不存在，已跳过")
            updated_lines.append(original_line)
            error_count += 1
            continue

        phrase = parts[phrase_col].strip()

        # 提取原始权重
        original_weight = parts[weight_col].strip() if weight_col < len(parts) else ""

        # 在拖入文件中查找
        if phrase in drag_in_mapping:
            new_weight = drag_in_mapping[phrase]

            # 如果权重相同，不需要修改
            if original_weight == new_weight:
                updated_lines.append(original_line)
                continue

            # 替换权重列
            parts[weight_col] = new_weight

            # 重新构建行
            updated_line = '\t'.join(parts) + '\n'
            updated_lines.append(updated_line)

            # 记录被修改的原始行内容
            modified_lines.append(line_content)

            updated_count += 1
        else:
            # 未找到，保持原样
            updated_lines.append(original_line)
            not_found_count += 1

    # 备份基础文件
    timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    backup_file = os.path.join(record_dir, f"phrase_weight_backup_{timestamp}.txt")

    try:
        # 读取原始基础文件内容用于备份
        with open(base_file, 'r', encoding='utf-8') as f:
            original_content = f.read()

        with open(backup_file, 'w', encoding='utf-8') as f:
            f.write(original_content)
    except Exception as e:
        print(f"警告: 备份基础文件失败: {str(e)}")
        backup_file = None

    # 写入更新后的基础文件
    try:
        with open(base_file, 'w', encoding='utf-8') as f:
            # 写入注释行
            for line in base_comment_lines:
                f.write(line)

            # 写入数据行
            for line in updated_lines:
                f.write(line)

        print(f"成功更新基础文件: {base_file}")
        print(f"替换了 {updated_count} 行数据")
        print(f"未找到匹配的词组: {not_found_count} 个")
        print(f"处理错误: {error_count} 行")

        # 创建更新记录
        script_name = os.path.splitext(os.path.basename(__file__))[0]
        record_file = create_update_record(
            record_dir, script_name, timestamp, "phrase_weight.txt",
            updated_count, not_found_count, error_count,
            "用拖入文件替换基础文件", os.path.basename(drag_in_file),
            modified_lines, backup_file, original_content
        )

        if record_file:
            print(f"更新记录已保存到: {record_file}")

        return True

    except Exception as e:
        print(f"写入基础文件时发生错误: {str(e)}")
        return False

def replace_weights_direction2(drag_in_file, base_mapping, record_dir):
    """方向2：用基础文件替换拖入文件中的权重"""
    print("\n正在执行替换方向2：用基础文件替换拖入文件中的权重")

    # 解析拖入文件
    drag_in_comment_lines, drag_in_data_lines, drag_in_column_types, drag_in_mapping, drag_in_indices = load_file_with_column_detection(drag_in_file)

    if not drag_in_data_lines:
        print("错误: 拖入文件中没有数据行")
        return False

    # 处理数据行
    updated_lines = []
    updated_count = 0
    not_found_count = 0
    error_count = 0
    modified_lines = []

    for line_num, line_content, original_line in drag_in_data_lines:
        # 跳过空行
        if not line_content.strip():
            updated_lines.append(original_line)
            continue

        # 检查分隔符
        if '\t' not in line_content:
            print(f"警告: 拖入文件第{line_num+1}行未找到Tab分隔符，已跳过: {line_content}")
            updated_lines.append(original_line)
            error_count += 1
            continue

        # 分割行
        parts = line_content.split('\t')

        # 跳过没有足够列的行
        if len(parts) < 2:
            print(f"警告: 拖入文件第{line_num+1}行列数不足，已跳过")
            updated_lines.append(original_line)
            error_count += 1
            continue

        # 验证行数据
        errors = validate_row_by_column_types(parts, drag_in_column_types)
        if errors:
            print(f"警告: 拖入文件第{line_num+1}行数据验证失败: {'; '.join(errors)}")
            # 继续尝试，可能只是列顺序问题

        # 查找该行的词组列和权重列
        phrase_col, weight_col = find_columns_by_type_for_row(parts, drag_in_column_types)

        if phrase_col is None:
            # 尝试查找包含汉字的列作为词组列
            for col_idx, cell in enumerate(parts):
                cell = cell.strip()
                if cell and re.search(r'[\u4e00-\u9fff]', cell):
                    phrase_col = col_idx
                    break

        if weight_col is None:
            # 尝试查找纯数字的列作为权重列
            for col_idx, cell in enumerate(parts):
                cell = cell.strip()
                if cell and re.fullmatch(r'-?\d+', cell):
                    weight_col = col_idx
                    break

        if phrase_col is None:
            print(f"警告: 拖入文件第{line_num+1}行词组列不存在，已跳过")
            updated_lines.append(original_line)
            error_count += 1
            continue

        if weight_col is None:
            print(f"警告: 拖入文件第{line_num+1}行权重列不存在，已跳过")
            updated_lines.append(original_line)
            error_count += 1
            continue

        phrase = parts[phrase_col].strip()

        # 提取原始权重
        original_weight = parts[weight_col].strip() if weight_col < len(parts) else ""

        # 在基础文件中查找
        if phrase in base_mapping:
            new_weight = base_mapping[phrase]

            # 如果权重相同，不需要修改
            if original_weight == new_weight:
                updated_lines.append(original_line)
                continue

            # 替换权重列
            parts[weight_col] = new_weight

            # 重新构建行
            updated_line = '\t'.join(parts) + '\n'
            updated_lines.append(updated_line)

            # 记录被修改的原始行内容
            modified_lines.append(line_content)

            updated_count += 1
        else:
            # 未找到，保持原样
            updated_lines.append(original_line)
            not_found_count += 1

    # 备份拖入文件
    timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    base_name = os.path.splitext(os.path.basename(drag_in_file))[0]
    backup_file = os.path.join(record_dir, f"{base_name}_backup_{timestamp}.txt")

    try:
        # 读取原始拖入文件内容用于备份
        with open(drag_in_file, 'r', encoding='utf-8') as f:
            original_content = f.read()

        with open(backup_file, 'w', encoding='utf-8') as f:
            f.write(original_content)
    except Exception as e:
        print(f"警告: 备份拖入文件失败: {str(e)}")
        backup_file = None

    # 写入更新后的拖入文件
    try:
        with open(drag_in_file, 'w', encoding='utf-8') as f:
            # 写入注释行
            for line in drag_in_comment_lines:
                f.write(line)

            # 写入数据行
            for line in updated_lines:
                f.write(line)

        print(f"成功更新拖入文件: {drag_in_file}")
        print(f"替换了 {updated_count} 行数据")
        print(f"未找到匹配的词组: {not_found_count} 个")
        print(f"处理错误: {error_count} 行")

        # 创建更新记录
        script_name = os.path.splitext(os.path.basename(__file__))[0]
        record_file = create_update_record(
            record_dir, script_name, timestamp, os.path.basename(drag_in_file),
            updated_count, not_found_count, error_count,
            "用基础文件替换拖入文件", "phrase_weight.txt",
            modified_lines, backup_file, original_content
        )

        if record_file:
            print(f"更新记录已保存到: {record_file}")

        return True

    except Exception as e:
        print(f"写入拖入文件时发生错误: {str(e)}")
        return False

def get_file_path():
    """获取用户输入的文件路径"""
    file_path = input().strip()

    # 检查是否输入q退出
    if file_path.lower() == 'q':
        return 'q'

    # 处理拖放文件时可能的引号
    if file_path.startswith('"') and file_path.endswith('"'):
        file_path = file_path[1:-1]
    elif file_path.startswith("'") and file_path.endswith("'"):
        file_path = file_path[1:-1]

    return file_path

def main():
    """主函数"""
    print("=" * 60)
    print("文件权重更新工具")
    print("程序名称: 智能文件权重同步器")
    print("主要功能: 在两个文件之间同步权重信息，自动识别列类型")
    print("支持格式: .txt、.yaml")
    print("列类型定义:")
    print("  - 词组列: 可以是汉字、字母、数字、标点的任意组合")
    print("  - 编码列: 只能是小写英文字母")
    print("  - 权重列: 只能是整数")
    print("特殊功能:")
    print("  - 支持列顺序混乱的文件")
    print("  - 自动分析每行的列类型")
    print("  - 智能匹配词组和权重")
    print("输入要求:")
    print("  1. 文件必须包含词组列和权重列，编码列为可选")
    print("  2. Tab分隔各列")
    print("  3. '...'之前为注释行，其后为数据行")
    print("处理规则:")
    print("  1. 自动检测文件中的列类型（词组、编码、权重）")
    print("  2. 根据选择的替换方向执行权重同步")
    print("  3. 仅当词组列的值完全匹配时进行替换")
    print("  4. 权重相同时，不进行替换")
    print("  5. 未找到匹配词组时，保持原样")
    print("  6. 自动验证各列类型，类型错误行将被跳过")
    print("=" * 60)
    print()

    # 检查phrase_weight.txt文件是否存在
    base_file = "phrase_weight.txt"
    if not os.path.exists(base_file):
        print(f"错误: 基础文件 '{base_file}' 不存在")
        print("请确保phrase_weight.txt文件与程序在同一目录下")
        print("\n按回车键退出...")
        input()
        return

    print(f"基础文件: {base_file}")

    # 加载基础文件
    print("\n正在加载基础文件...")
    base_comment_lines, base_data_lines, base_column_types, base_mapping, base_indices = load_file_with_column_detection(base_file)
    print(f"基础文件中词组数量: {len(base_mapping)}")

    # 设置记录文件保存目录
    record_dir = r"D:\OneDrive\Backup\RimeSync\update_record"
    print(f"备份或更新日志文件将保存到: {record_dir}")

    # 文件处理计数
    file_count = 0
    empty_input_count = 0

    # 主循环
    while True:
        print(f"\n{'='*60}")
        print(f"文件 {file_count+1}")
        print('='*60)

        # 选择替换方向
        print("请选择替换方向:")
        print("  1. 用拖入文件替换基础文件(phrase_weight.txt)中的权重")
        print("  2. 用基础文件(phrase_weight.txt)替换拖入文件中的权重")
        print("  (输入q或连续两个回车退出)")

        direction = ""
        direction_empty_count = 0

        while True:
            choice = input("请选择 (1/2): ").strip()

            if choice.lower() == 'q':
                print("\n用户输入q，程序退出。")
                return

            if not choice:
                direction_empty_count += 1
                if direction_empty_count >= 2:
                    print("\n连续两个空输入，程序退出。")
                    return
                else:
                    print("输入为空，请重新输入选择。")
                    continue
            else:
                direction_empty_count = 0

            if choice == '1':
                direction = 1
                break
            elif choice == '2':
                direction = 2
                break
            else:
                print("输入错误，请输入1或2")

        # 获取拖入文件路径
        print("\n请拖入文件或输入文件路径 (输入q或连续两个回车退出):")

        file_path_empty_count = 0

        while True:
            file_path = get_file_path()

            if file_path == 'q':
                print("\n用户输入q，程序退出。")
                return

            if not file_path:
                file_path_empty_count += 1
                if file_path_empty_count >= 2:
                    print("\n连续两个空输入，程序退出。")
                    return
                else:
                    print("输入为空，请重新输入文件路径。")
                    continue
            else:
                file_path_empty_count = 0

            # 检查文件是否存在
            if not os.path.exists(file_path):
                print(f"错误: 文件 '{file_path}' 不存在，请重新输入。")
                continue

            # 检查文件扩展名
            if not (file_path.endswith('.txt') or file_path.endswith('.yaml')):
                print("警告: 文件扩展名不是 .txt 或 .yaml，但仍尝试处理")

            break

        # 根据选择的方向执行相应的替换操作
        if direction == 1:
            success = replace_weights_direction1(file_path, base_file, record_dir)
        else:
            success = replace_weights_direction2(file_path, base_mapping, record_dir)

        if success:
            print(f"\n✓ 文件处理成功！")
            file_count += 1

    if file_count > 0:
        print(f"\n总共处理了 {file_count} 个文件。")
        print(f"所有记录文件已保存在: {record_dir}")
    else:
        print("没有处理任何文件。")
    
    print("\n程序退出。")

if __name__ == "__main__":
    main()