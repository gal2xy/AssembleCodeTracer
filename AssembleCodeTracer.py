import re
from typing import List, Tuple, Set


# 只考虑一般程序员能够修改的寄存器，不考虑由系统分配和修改的寄存器（如rip, rbp, rsp, es, cs等）
instructions_db = {
    # mov类指令
    'mov': {
        'insns': ['mov', 'movsx', 'movzx', 'movsxd'],
        'has_types': False,
        'def_exp_index': [0],
        'use_exp_index': [1],
        'def_imp_reg': [],
        'use_imp_reg': [],
    },
    # movs类指令
    'movs': {
        'insns': ['movsb', 'movsbyte', 'movsw', 'movsword', 'movsd', 'movsdword', 'movsq', 'movsqword'],
        'has_types': False,
        'def_exp_index': [],
        'use_exp_index': [],
        'def_imp_reg': ['rsi', 'rdi', '[rdi]'],
        'use_imp_reg': ['rsi', 'rdi', '[rsi]', '[rdi]', 'ds', 'es', 'rflags'],
    },
    # cmov类指令
    'cmov': {
        # 遇到cmov指令，需要分成两条路径进行探索
        # 1: if the condiction is satisfied, it belongs to use_and_def.Actually,
        #    it's first operand is def, and both operands are use, also uses rflags.
        # 2: if the condiction is unsatisfied, it belongs to only_use, because it uses rflags
        # 解决方法: def集合选择元素最少的, use集合选择元素最多的
        'insns': ['cmova', 'cmovae', 'cmovb', 'cmovbe', 'cmovc', 'cmovnc', 'cmove', 'cmovne',
                  'cmovz', 'cmovnz', 'cmovg', 'cmovge', 'cmovl', 'cmovle', 'cmovnae',
                  'cmovnb', 'cmovna', 'cmovno', 'cmovo', 'cmovp', 'cmovnp', 'cmovs', 'cmovns'],
        'has_types': False,
        'def_exp_index': [0],
        'use_exp_index': [1],
        'def_imp_reg': [],
        'use_imp_reg': ['rflags'],
    },
    # setcc指令（不存在与cmovcc指令相同的尴尬境遇，因为setcc指令根据条件选择置0或1，无论哪种情况，都会更改指令中的寄存器）
    'setcc': {
        'insns': ['sete', 'setz', 'setne', 'setnz', 'setg', 'setnle', 'setge', 'setnl',
                  'setl', 'setnge', 'setle', 'setng', 'seta', 'setnbe', 'setae', 'setnb',
                  'setb', 'setnae', 'setbe', 'setna', 'seto', 'setno', 'sets', 'setns',
                  'setp', 'setpe', 'setnp', 'setpo'],
        'has_types': False,
        'def_exp_index': [0],
        'use_exp_index': [],
        'def_imp_reg': [],
        'use_imp_reg': ['rflags'],
    },
    # 运算类指令
    'cacluate_1': {
        'insns': ['inc', 'dec', 'neg', 'not'],
        'has_types': False,
        'def_exp_index': [0],
        'use_exp_index': [0],
        'def_imp_reg': ['rflags'],
        'use_imp_reg': [],
    },
    'cacluate_2': {
        'insns': ['add', 'sub', 'adc', 'sbb', 'and', 'or', 'xor',
                  'shl', 'shr', 'sal', 'sar', 'rol', 'ror', 'rcl', 'rcr'],
        'has_types': False,
        'def_exp_index': [0],
        'use_exp_index': [0, 1],
        'def_imp_reg': ['rflags'],
        'use_imp_reg': [],
    },
    'mul': {
        'insns': ['mul'],
        'has_types': False,
        'def_exp_index': [],
        'use_exp_index': [0],
        'def_imp_reg': ['rax', 'rflags'],
        'use_imp_reg': ['rax'],
    },
    'imul': {
        'insns': ['imul'],
        'has_types': True,
        'types': {
            1: {
                'def_exp_index': [],
                'use_exp_index': [0],
                'def_imp_reg': ['rax', 'rflags'],
                'use_imp_reg': ['rax'],
            },
            2: {
                'def_exp_index': [0],
                'use_exp_index': [0, 1],
                'def_imp_reg': ['rflags'],
                'use_imp_reg': [],
            },
            3: {
                'def_exp_index': [0],
                'use_exp_index': [0, 1, 2],
                'def_imp_reg': ['rflags'],
                'use_imp_reg': [],
            }
        },
    },
    'div': {
        'insns': ['div', 'idiv'],
        'has_types': False,
        'def_exp_index': [],
        'use_exp_index': [0],
        'def_imp_reg': ['rax', 'rdx', 'rflags'],# 未考虑8bit的除法
        'use_imp_reg': ['rax'],
    },
    'test': {
        'insns': ['test'],
        'has_types': False,
        'def_exp_index': [],
        'use_exp_index': [0, 1],
        'def_imp_reg': ['rflags'],
        'use_imp_reg': [],
    },
    # 比较指令
    'cmp': {
        'insns': ['cmp'],
        'has_types': False,
        'def_exp_index': [],
        'use_exp_index': [0, 1],
        'def_imp_reg': ['rflags'],
        'use_imp_reg': [],
    },
    # 跳转指令
    'jmp': {
        'insns': ['jmp'],
        'has_types': False,
        'def_exp_index': [],
        'use_exp_index': [0],
        'def_imp_reg': [],
        'use_imp_reg': [],
    },
    'jcc': {
        'insns': ['ja', 'jae', 'jb', 'jbe', 'jc', 'je', 'jz', 'jg', 'jge', 'jl', 'jle', 'jna', 'jnae',
                  'jnb', 'jnbe',  'jnc', 'jne', 'jng', 'jnge', 'jnl', 'jnle', 'jno', 'jnp', 'jns', 'jnz',
                  'jo', 'jp', 'jpe', 'jpo', 'js'],
        'has_types': False,
        'def_exp_index': [],
        'use_exp_index': [0],
        'def_imp_reg': [],
        'use_imp_reg': ['rflags'],
    },
    # 循环指令
    'loop': {
        'insns': ['loop'],
        'has_types': False,
        'def_exp_index': [],
        'use_exp_index': [0],
        'def_imp_reg': [],
        'use_imp_reg': ['rcx'],
    },
    'loopcc': {
        'insns': ['loope', 'loopz', 'loopne', 'loopnz'],
        'has_types': False,
        'def_exp_index': [],
        'use_exp_index': [0],
        'def_imp_reg': [],
        'use_imp_reg': ['rcx', 'rflags'],
    },
    #
    'lea': {
        'insns': ['lea'],
        'has_types': False,
        'def_exp_index': [0],
        'use_exp_index': [1],
        'def_imp_reg': [],
        'use_imp_reg': [],
    },
    # 栈操作指令
    'push': {
        'insns': ['push'],
        'has_types': False,
        'def_exp_index': [],
        'use_exp_index': [0],
        'def_imp_reg': [],# 暂不考虑rsp寄存器以及相关内存
        'use_imp_reg': [],
    },
    'pop': {
        'insns': ['pop'],
        'has_types': False,
        'def_exp_index': [0],
        'use_exp_index': [],
        'def_imp_reg': [],
        'use_imp_reg': [],# 暂不考虑rsp寄存器以及相关内存
    },
    # 函数调用
    'call': {
        'insns': ['call'],
        'has_types': False,
        # 暂不考虑call指令所带来的寄存器变化
        'def_exp_index': [],
        'use_exp_index': [0],
        'def_imp_reg': [],
        'use_imp_reg': [],
    },
    'retn': {
        'insns': ['retn'],
        'has_types': False,
        # 暂不考虑retn指令所带来的寄存器变化
        'def_exp_index': [],
        'use_exp_index': [],
        'def_imp_reg': [],
        'use_imp_reg': [],
    }
}

# 建立寄存器数据库
registers_db = {
    'rax': ['rax', 'eax', 'ax', 'al', 'ah'],
    'rbx': ['rbx', 'ebx', 'bx', 'bl', 'bh'],
    'rcx': ['rcx', 'ecx', 'cx', 'cl', 'ch'],
    'rdx': ['rdx', 'edx', 'dx', 'dl', 'dh'],
    'rsi': ['rsi', 'esi', 'si', 'sil'],
    'rdi': ['rdi', 'edi', 'di', 'dil'],
    'rbp': ['rbp', 'ebp', 'bp', 'bpl'],
    'rsp': ['rsp', 'esp', 'sp', 'spl'],
    'r8': ['r8', 'r8d', 'r8w', 'r8b'],
    'r9': ['r9', 'r9d', 'r9w', 'r9b'],
    'r10': ['r10', 'r10d', 'r10w', 'r10b'],
    'r11': ['r11', 'r11d', 'r11w', 'r11b'],
    'r12': ['r12', 'r12d', 'r12w', 'r12b'],
    'r13': ['r13', 'r13d', 'r13w', 'r13b'],
    'r14': ['r14', 'r14d', 'r14w', 'r14b'],
    'r15': ['r15', 'r15d', 'r15w', 'r15b'],
    # 以下感觉考虑过多了
    'rip': ['rip'],
    'cs': ['cs'],
    'ds': ['ds'],
    'es': ['es'],
    'ss': ['ss']
}


# 解析内存操作数中的寄存器
def findRegInMemOp(operand: str):

    pattern = r'\b([er]?([abcds][xlhpi]|bp|sp)|r[89]|r1[0-5])\b'

    registers = set([])
    # 查找内存操作数中的所有寄存器
    registersInOperand = re.findall(pattern, operand)
    print(f'find registers in memory operand: {registersInOperand}')# [('rbp', 'bp')]
    # 从输出结果上来看，貌似是同一寄存器一个元组，如果是的话，以下操作可以简化
    for registersTuple in registersInOperand:
        for register in registersTuple:
            fullName = findFullRegisterName(register)
            if fullName is not None:
                registers.add(fullName)# 其实直接加入即可，因为后续会统一转成寄存器全称，而且是集合，所以不存在重复情况
            else:
                print(f'Warning!!! Unknow register: {register}, may be you need define it in registers_db')

    print(f'memory operand: {operand}, extract registers: {registers}')
    return registers


# 解析操作数的类型：寄存器、立即数、内存引用
def parseOperand(operand: str):

    operand = operand.strip()

    # 判断是否为寄存器.后一个捕获r8~r15相关寄存器
    if re.match(r'^[er]?[abcds][xlhpi]$', operand) or re.match(r'(r[89]|r1[0-5])[dwb]?', operand):
        return 'register'
    # 判断是否为内存操作数
    elif re.match(r'^\[.*\]$', operand):
        return 'memory'
    # 判断是否为立即数
    elif re.match(r'(?:0[xX])?[0-9A-Fa-f]+h?', operand):
        return 'immediate'
    return 'unknown'


# 根据寄存器名找寄存器名(r开头的)
def findFullRegisterName(register: str):

    for fullName, registers in registers_db.items():
        if register in registers:
            return fullName

    return None


# 删除操作数中的关键字(例如 ptr, offset)
def deleteKeyWords(operands: List):

    newOperands = []
    pattern = r'\b(byte|ptr|offset|short|far|near)\b'

    # 使用正则表达式删除关键字
    for operand in operands:
        newOperand = re.sub(pattern, '', operand).strip()
        newOperands.append(newOperand)

    return newOperands


# 借助指令数据库获取指令中的def和use集合
def getDefAndUseSet(insnsDic: dict, operands: List):

    defSet = set([])
    useSet = set([])
    # 先找显式定义的
    # 遍历需要加入到def集合中的操作数索引
    for pos in insnsDic['def_exp_index']:
        # 根据操作数的类型决定是否添加到def集合中
        operandType = parseOperand(operands[pos])
        if operandType == 'register':  # 寄存器直接加入
            defSet.add(operands[pos])
        elif operandType == 'memory':  # 内存操作数
            defSet.add(operands[pos])
            # 内存操作数借助的寄存器放入useSet中
            registers = findRegInMemOp(operands[pos])
            useSet.update(registers)
        else:  # 未知类型，例如label标签
            continue
    # 再找隐式定义的
    for register in insnsDic['def_imp_reg']:
        defSet.add(register)

    # useSet同理
    for pos in insnsDic['use_exp_index']:
        # 根据操作数的类型决定是否添加到use集合中
        operandType = parseOperand(operands[pos])
        if operandType == 'register':  # 寄存器直接加入
            useSet.add(operands[pos])
        elif operandType == 'memory':  # 内存操作数，则读取表达式中的寄存器并加入
            useSet.add(operands[pos])
            registers = findRegInMemOp(operands[pos])
            useSet.update(registers)
        else:  # 未知类型，例如label标签
            continue

    for register in insnsDic['use_imp_reg']:
        useSet.add(register)

    # 由于寄存器存在高低位之分，所以转成最大的寄存器的名称
    newDefSet = set([])
    for register in defSet:
        fullName = findFullRegisterName(register)
        if fullName is not None:
            newDefSet.add(fullName)
        else:# 其他类型的操作数，例如[rbp+var_4], rflags
            newDefSet.add(register)

    newUseSet = set([])
    for register in useSet:
        fullName = findFullRegisterName(register)
        if fullName is not None:
            newUseSet.add(fullName)
        else:
            newUseSet.add(register)

    return newDefSet, newUseSet


# 分析指令中操作符和操作数，并获取def和use集合
def analyzeInstruction(instruction: str):

    instruction = instruction.strip().rstrip('; ')
    # 以一个或多个连续的空格分割指令为两部分：操作符、操作数
    # 由于操作数可能是0个、1个或多个，因此借助','进行分割
    token = re.split(r'\s+', instruction, maxsplit=1)
    print(f'token: {token}')
    if len(token) == 1:  # 无/无显式操作数指令
        operator = token[0]
        operands = []
    else:
        operator = token[0]
        operands = token[1].split(',')
        operands = [operand.strip() for operand in operands]  # 去除多余空格

    # 清除操作数中的ptr byte 等
    operands = deleteKeyWords(operands)
    print(f'operator: {operator} , operands: {operands}')

    # 根据操作符来决定def和use集合
    for category, insnsDic in instructions_db.items():
        if operator in insnsDic['insns']:
            # defSet = set([])
            # useSet = set([])
            if insnsDic['has_types']:# 存在多种指令格式
                # 根据操作数个数寻找对应指令格式
                operandNumber = len(operands)
                CorresInsnsDic = insnsDic['types'][operandNumber]
                defSet, useSet = getDefAndUseSet(CorresInsnsDic, operands)
            else:
                defSet, useSet = getDefAndUseSet(insnsDic, operands)
            # 需要存储的是全称寄存器或者是寄存器编号!!!!!!
            return defSet, useSet

    print(f'Warning!!! Unknow instruction: {instruction}. You need define it in instructions_db')
    return None


# 跟踪既定汇编指令的相关汇编指令
def traceInstructionsInBlock(instructions: List, defAndUseSet: List[Tuple[Set, Set]], startPos: int, traceSet=None):
    # trace = trace - def + use. 集合运算
    if traceSet is None:
        traceSet = defAndUseSet[startPos][1]# trace = use

    relevantInsPos = set([startPos])
    print(f'traceSet: {traceSet}')

    currPos = startPos - 1
    while currPos >= 0 or traceSet is None:# 结束标志: tarce集合为空, 或者分析到达基本块首部
        currDefSet = defAndUseSet[currPos][0]
        currUseSet = defAndUseSet[currPos][1]
        print(f'instructions: {instructions[currPos]}, currDefSet = {currDefSet}, currUseSet = {currUseSet}')
        # 求 traceSet 和 currDefSet 的交集，如果不为空，则当前指令是相关指令
        intersectionSet = traceSet & currDefSet
        print(f'交集: {intersectionSet}')
        if len(intersectionSet) != 0:# 是相关指令
            if instructions[currPos].startswith('cmov'): # cmov指令特殊，应分两种情况进行讨论
                # 此情况是条件不成立，cmov不执行。
                # 不减交集, 而是直接并use集
                newTraceSet = traceSet | set(['rflags'])
                # 在该情况的基础上进行探索
                anotherRelevantInsPos = traceInstructionsInBlock(instructions, defAndUseSet, currPos, traceSet=newTraceSet)
                relevantInsPos.update(anotherRelevantInsPos)
            # 以下是cmov执行的情况, 以及除cmov指令外的其他指令
            # 做差集, 减去被定义的操作数
            traceSet = traceSet - intersectionSet
            # 做并集，加入后续需要跟踪的操作数
            traceSet = traceSet | currUseSet
            print(f'traceSet: {traceSet}')

            # 添加当前指令到相关指令集中
            relevantInsPos.add(currPos)

        currPos -= 1

    return relevantInsPos


# 以下两个函数应定义在去混淆模块中
def nopUselessInstruction():
    pass


def patchBlock():
    pass


# 去混淆模块接入这个接口函数，获取相关指令，进行后续的patch
def startTracer(instructions: List, traceInstruction: str):

    defAndUseSet = []

    print(f'******************** extract def set and use set from instructions ********************')
    for instruction in instructions:
        result = analyzeInstruction(instruction)
        if result is not None:
            defAndUseSet.append(result)
            defSet = result[0]
            useSet = result[1]
            print(f'{instruction}, def = {defSet}, use = {useSet}')

        print()

    print(f'******************** trace relevant instructions ********************')
    print(f'tracing the instruction: {traceInstruction}')
    relevantInsnsPos = traceInstructionsInBlock(instructions, defAndUseSet, instructions.index(traceInstruction))

    print('******************** found relevant instructions ********************')
    for pos in relevantInsnsPos:
        print(instructions[pos])

    return relevantInsnsPos


if __name__ == "__main__":

    # 虚假控制流混淆的冗余汇编代码
    # instructions = [
    #     'mov     rax, [rbp+var_10]',
    #     'movsxd  rcx, [rbp+var_14]',
    #     'movsx   eax, byte ptr [rax+rcx]',
    #     'add     eax, [rbp+var_18]',
    #     'mov     [rbp+var_18], eax',
    #     'mov     rax, offset x',
    #     'mov     eax, [rax]',
    #     'mov     rcx, offset y',
    #     'mov     ecx, [rcx]',
    #     'mov     edx, eax',
    #     'sub     edx, 1',
    #     'imul    eax, edx',
    #     'and     eax, 1',
    #     'cmp     eax, 0',
    #     'setz    al',
    #     'cmp     ecx, 0Ah',
    #     'setl    cl',
    #     'or      al, cl',
    #     'test    al, 1',
    #     'jnz     loc_401235'
    # ]
    # traceInstruction = 'jnz     loc_401235'

    # 控制流平坦化混淆的冗余汇编代码
    # 这个去冗余代码有误，原因在于假代码利用了真实代码的汇编指令来更改rflags，从而将真实代码的汇编指令误认为是冗余指令
    # instructions = [
    #     'mov     rax, [rbp + var_10];',  # 真实代码
    #     'movsx   edx, byte ptr [rax + 3];',  # 真实代码
    #     'mov     eax, 7A39EAC0h;',
    #     'mov     ecx, 9BEE23F6h;',
    #     'cmp     edx, 65h;',  # 真实代码
    #     'cmovl   eax, ecx;',
    #     'mov      [rbp + var_1C], eax;',
    #     'jmp      loc_401418;',
    # ]
    # traceInstruction = 'mov      [rbp + var_1C], eax;'

    # 另一个控制流平坦化混淆的冗余代码
    # 全是冗余代码，需要对cmov指令单独分两种情况分析，否则会有遗漏
    instructions = [
        'mov     edx, [rbp+var_4];',
        'mov     eax, 7A39EAC0h;',
        'mov     ecx, 9BEE23F6h;',
        'cmp     edx, 2;',
        'cmovnz  eax, ecx;',
        'mov      [rbp + var_1C], eax;',
        'jmp      loc_401418;',
    ]
    traceInstruction = 'mov      [rbp + var_1C], eax;'

    relevantInsnsPos = startTracer(instructions, traceInstruction)