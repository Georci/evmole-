# 关键类 

# 描述：在EVM的calldata中，除了function_selector以外的其他数据，每一个都是Arg类,或者是Arg类的子类
class Arg(bytes):
    offset: int #该数据在CALLDATA中的位置
    dynamic: bool # 该数据是否为动态数据

    # 这里是对于一个战中的处理数据而言，获取其序号offset，是否是动态数据dynamic,dynamic默认为静态，以及具体的数据bytes,默认为32字节的0
    def __new__(cls, *, offset: int, dynamic: bool = False, val: bytes = b'\x00' * 32):
        v = super().__new__(cls, val)
        v.dynamic = dynamic
        v.offset = offset
        return v

    def __repr__(self):
        return f'arg({self.offset},{self.dynamic})'
## Arg类：作为CallData中每一个数据的基础类(出函数选择器外)，如果一个bytes类型的数据被CALLDATALOAD操作处理后，将该bytes类型数据升级为Arg类。拥有两个属性1.offset 该数据在CallData中的位置 2.dynamic 该数据是否是动态数据
## Arg类方法：1._new_()该方法在创建一个新的Arg类的时候会自动执行，offset默认为int类型，dynamic默认为false,val表示该Arg类型的值，默认为32字节的0 2.__repr__()该方法打印当前数据的信息
## 实际应用：在本项目中，EVM执行时CALLDATALOAD操作处理的每一个数据至少都是Arg，可能是Arg的子类
========================================================================================================================================================================================
# 描述：可能是想用来作为描述动态数据长度的类
class ArgDynamicLength(bytes):
    offset: int

    def __new__(cls, *, offset: int):
        # v的最低字段是1,其余全是0
        v = super().__new__(cls, (1).to_bytes(32, 'big'))
        v.offset = offset
        return v

    def __repr__(self):
        return f'dlen({self.offset})'

## ArgDynamicLength类：如果一个Arg类的数据被CALLDATALOAD操作码处理了，则将该Arg类型的数据从Arg类升级为ArgDynamicLength类型数据。
========================================================================================================================================================================================
class ArgDynamic(bytes):
    offset: int

    def __new__(cls, *, offset: int, val: bytes):
        v = super().__new__(cls, val)
        v.offset = offset
        return v

    def __repr__(self):
        return f'darg({self.offset})'
## ArgDynamic类：如果一个Arg类的数据被ADD操作码进行了处理，且该Arg类型的数据不是函数选择器，则将该Arg类型的数据升级到ArgDynamic类型。
========================================================================================================================================================================================

class IsZeroResult(bytes):
    offset: int
    dynamic: bool

    def __new__(cls, *, offset: int, dynamic: bool, val: bytes):
        v = super().__new__(cls, val)
        v.offset = offset
        v.dynamic = dynamic
        return v

    def __repr__(self):
        return f'zarg({self.offset})'
## IsZeroResult类：如果一个Arg类的数据被ISZERO操作码进行了处理，则将该Arg类型的数据升级到IsZeroResult类型
========================================================================================================================================================================================
# 关键函数：

# 描述：整个function_arguments的运行流程
'''step1：该函数首先根据输入的字节码以及函数选择器初始化一个EVM，
   step2：在EVM没有停止的情况下，去执行每一个操作码(指令)，具体的执行逻辑在vm.py文件的_exec_opcode()函数中
   step3：一个操作执行完之后返回值会被放到ret中，此时栈的状态被更新到操作执行之后的状态
   step4：根据ret中的执行信息，以及栈中的状态去执行具体的参数类型判断操作(此过程同样会对栈中的状态发生改变)
'''



def function_arguments(code: bytes | str, selector: bytes | str, gas_limit: int = int(1e4)) -> str:
    bytes_selector = to_bytes(selector)
    vm = Vm(code=to_bytes(code), calldata=CallData(bytes_selector)) # 传入当前合约的runtime code 创建执行当前合约字节码的EVM，初始化的时候calldata中应该只包含函数选择器，每次处理的是单个函数
    gas_used = 0 # 消耗的gas，我认为没用 
    inside_function = False # 判断当前操作码是否是在函数里面，vm虚拟机仅仅只处理函数里面的字节码
    args: dict[int, str] = {} # 创建参数字典，在calldata中的位置作为键，该参数的类型作为值
    
    # 在这个地方要想停止整个EVM，必须要：1.gas消耗完 2.报错
    while not vm.stopped:
        try:
            # 关键步骤：调用EVM中的step()函数，该函数返回一个元组ret：[第一个元素是当前执行的字节码currentOp,第二个元素是当前操作消耗的gas gas_used,第三个元素是从栈顶弹出的当前字节码的操作数operand1,第四个元素是从栈顶弹出的当前字节码的操作数operand2]
            # 注意：该过程中的operand1和operand2并不一定存在，可能为空“_”，第一个原因是有些字节码本身不存在操作数，第二个原因是有些字节码的操作数对后面的代码而言不重要。
            ret = vm.step()
            gas_used += ret[1]
            # 当前操作消耗的gas大于gaslimit
            if gas_used > gas_limit:
                # raise Exception(f'gas overflow: {gas_used} > {gas_limit}')
                print("gas overflow!")
                break
            if inside_function:
                # print(vm, '\n')
                # print(ret)
                pass
        # 抛出异常
        except (StackIndexError, UnsupportedOpError) as ex:
            _ = ex
            print(ex)
            break

        '''这段操作用来判断当前字节码是在函数中还是在函数外'''
        if inside_function is False:
            # EQ判断是否相等，XOR异或操作，SUB减操作都能被用来作为判断条件
            if ret[0] in {Op.EQ, Op.XOR, Op.SUB}:
                p = int.from_bytes(vm.stack.peek(), 'big')
                # 这个地方是要比较是否选择当前函数，要选择当前函数执行，必然会使用判断条件判断是否要执行当前函数
                # 要求判断操作的第一个操作数operand1是以输入的函数选择器为结尾，如果条件满足 inside_function会被置为true，说明后续的字节码都是在函数中的操作
                if p == (1 if ret[0] == Op.EQ else 0):
                    inside_function = bytes(ret[2]).endswith(bytes_selector)
            continue


        #只有函数中的操作才会执行下面的操作
        match ret:
            # case (Op.CALLDATALOAD,_,_,_):
            #     print("1")

            # CALLDATASIZE没有操作数，返回calldata中数据的长度到栈中，然后这个地方的意思就是只要遇到CALLDATASIZE操作，就返回8192的长度到栈中
            case (Op.CALLDATASIZE, _):
                vm.stack.pop()
                vm.stack.push_uint(8192)

            # 如果对于Arg()类型的数据,有一个CALLDATALOAD将其作为了操作数,则能够直接说明其为bytes类型?
            # 并且将Arg()类型数据从栈中弹出,且推入ArgDynamicLength类型的数据
            case (Op.CALLDATALOAD, _, Arg() as arg):
                args[arg.offset] = 'bytes'
                vm.stack.pop()
                v = ArgDynamicLength(offset=arg.offset)
                vm.stack.push(v)

            case (Op.CALLDATALOAD, _, ArgDynamic() as arg):
                vm.stack.pop()
                v = Arg(offset=arg.offset, dynamic=True)
                vm.stack.push(v)

            # 在这个地方生成CALLDATALOAD的操作数Arg,这个地方创建Arg类型的数据时,只会以val = 0x0000..的方式创建
            # 所以Arg类型的变量都是CALLDATALOAD操作创建,但是是有可能由别的操作升级
            # 所以这个函数会将整个CALLDATA中所有的数据全都标为Arg()类数据
            case (Op.CALLDATALOAD, _, bytes() as offset):
                # offset作为CALLDATALOAD操作的操作数，表示当前CALLDATALOAD是从calldata中哪个位置取出数据
                off = int.from_bytes(offset, 'big')
                # calldata中前四个字节为函数选择器，我们所维护的calldata上限大小为2**32，所以参数数据应该是存储在calldata的4-2**32字节之间
                if off >= 4 and off < 2**32:
                    # CALLDATALOAD的执行逻辑在vm.py中执行，执行完之后 栈顶是CALLDATALOAD从calldata中加载的数据，此时将该数据弹出，升级为Arg类型的数据后重新推入栈顶，即只要是通过CALLDATALOAD从栈中加载出来的数据都是Arg类型
                    vm.stack.pop()
                    vm.stack.push(Arg(offset=off))
                    # 单凭CALLDATALOAD对一个bytes类型的数据进行输出，不能知道参数类型，因此该偏移量off对应的参数类型为空
                    args[off] = ''

            # 对于ADD操作是可以创造ArgDynamic类型的数据的
            case (Op.ADD, _, Arg() as cd, bytes() as ot) | (Op.ADD, _, bytes() as ot, Arg() as cd):
                # v是ADD操作的结果
                v = vm.stack.pop()
                # 如果ADD的除Arg的操作对象之外的另一个操作对象是4字节，则为Arg操作对象补充一个v之后重新放入栈中
                if int.from_bytes(ot, 'big') == 4:
                    # 此时知道Arg的具体值,将该信息传入到栈中
                    vm.stack.push(Arg(offset=cd.offset, val=v))
                # 所以这段代码并没有处理ADD操作之后的结果,只是完善一下ADD结果信息
                else:
                    # 如果该数据不是函数选择器,则将该数据升级为ArgDynamic
                    vm.stack.push(ArgDynamic(offset=cd.offset, val=v))

            case (Op.ADD, _, ArgDynamic() as cd, _) | (Op.ADD, _, _, ArgDynamic() as cd):
                v = vm.stack.pop()
                v = ArgDynamic(offset=cd.offset, val=v)
                vm.stack.push(v)

            # SHL(shift,value):将value(32字节的数据)向右移动shift位bit
            # 如果当前操作SHL使用了bytes类型和ArgDynamicLength的操作数，则说明ArgDynamicLength数据的类型为uint256[]
            case (Op.SHL, _, bytes() as ot, ArgDynamicLength() as arg):
                # int.from_bytes(ot, 'big')将bytes类型的数据转化为大端存储的int类型数据
                if int.from_bytes(ot, 'big') == 5:
                    args[arg.offset] = 'uint256[]'

            # MUL(a,b):将a，b相乘
            # 如果当前操作MUL使用了bytes类型和ArgDynamicLength类型的操作数，则说明ArgDynamicLength数据的类型为uint256[]
            case (Op.MUL, _, ArgDynamicLength() as arg, bytes() as ot) | (Op.MUL, _, bytes() as ot, ArgDynamicLength() as arg):
                if int.from_bytes(ot, 'big') == 32:
                    args[arg.offset] = 'uint256[]'

            # AND(a,b)
            # 对于任意CALLDATA中的数据,如果是该数据被ADD操作使用,则能判断该数据为address[]、uint<M>[]、bytes<M>[]三种类型
            # 如果是对于连续的同样值的数据,例如2222,大小端存储的差别只有在左右两端补0的位置
            case (Op.AND, _, Arg() as arg, bytes() as ot) | (Op.AND, _, bytes() as ot, Arg() as arg):
                v = int.from_bytes(ot, 'big')
                if v == 0:
                    pass
                # 下面这条判断语句用于检测0x0000ffff的情况
                # 如果是0x0000ffff的情况，v+1会将连续的f全部变成0，而将原本的0(最高位的)变成1，这样一来相与的结果就是0
                elif (v & (v + 1)) == 0:
                    # 0x0000ffff,以大端存储的方式进行存储
                    bl = v.bit_length()
                    if bl % 8 == 0:
                        # 所以确实不太容易检查address和uint160之间的区别
                        t = 'address' if bl == 160 else f'uint{bl}'
                        args[arg.offset] = f'{t}[]' if arg.dynamic else t
                else:
                    # 0xffff0000
                    v = int.from_bytes(ot, 'little')
                    if (v & (v + 1)) == 0:
                        bl = v.bit_length()
                        if bl % 8 == 0:
                            t = f'bytes{bl // 8}'
                            # 这里直接根据规则推出bytes<M>[]或bytes<M>
                            args[arg.offset] = f'{t}[]' if arg.dynamic else t

            # 如果ISZERO操作码的操作对象是CALLDATA中的数据，则将该类型的数据转化为IsZeroResult类型的数据
            case (Op.ISZERO, _, Arg() as arg):
                v = vm.stack.pop()
                vm.stack.push(IsZeroResult(offset=arg.offset, dynamic=arg.dynamic, val=v))
            # 如果ISZERO操作处理了IsZeroResult类型的数据：
            case (Op.ISZERO, _, IsZeroResult() as arg):
                args[arg.offset] = 'bool[]' if arg.dynamic else 'bool'

            # 如果SIGNEXTEND操作处理了CALLDATA中的数据，则只能是int<M>或int<M>[]
            case (Op.SIGNEXTEND, _, s0, Arg() as arg):
                if s0 < 32:
                    t = f'int{(s0+1)*8}'
                    args[arg.offset] = f'{t}[]' if arg.dynamic else t

            # 只有bytes32类型数据会用到BYTE字节码
            case (Op.BYTE, _, _, Arg() as arg):
                if args[arg.offset] == '':
                    args[arg.offset] = 'bytes32'

            # case (Op.LT, _, CallDataArgument() as arg, _):
            #     args[arg.offset] = 'uint8' # enum

    return ','.join(v[1] if v[1] != '' else 'uint256' for v in sorted(args.items()))



