# 关键类 

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
## 实际应用：在本项目中，EVM执行时处理的每一个数据至少都是Arg，可能是Arg的子类
========================================================================================================================================================================================
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

def function_arguments(code: bytes | str, selector: bytes | str, gas_limit: int = int(1e4)) -> str:
    bytes_selector = to_bytes(selector)
    vm = Vm(code=to_bytes(code), calldata=CallData(bytes_selector)) # 传入当前合约的runtime code 创建执行当前合约字节码的EVM，初始化的时候calldata中应该只包含函数选择器，每次处理的是单个函数
    gas_used = 0 # 消耗的gas，我认为没用 
    inside_function = False # 判断当前操作码是否是在函数里面，vm虚拟机仅仅只处理函数里面的字节码
    args: dict[int, str] = {} # 创建参数字典，在calldata中的位置作为键，该参数的类型作为值
    
    # 这个地方的逻辑：遇到对应的函数选择器之后不会再将inside_function置为False，在这个地方要想停止整个EVM，必须要：1.gas消耗完 2.报错
    while not vm.stopped:
        try:
            ret = vm.step()
            gas_used += ret[1]
            if gas_used > gas_limit:
                # raise Exception(f'gas overflow: {gas_used} > {gas_limit}')
                print("gas overflow!")
                break
            if inside_function:
                # print(vm, '\n')
                # print(ret)
                pass
        except (StackIndexError, UnsupportedOpError) as ex:
            _ = ex
            print(ex)
            break

        '''这段操作用来判断当前字节码是在函数中还是在函数外'''
        if inside_function is False:
            # XOR异或操作，SUB减操作也能被用来作为判断条件
            if ret[0] in {Op.EQ, Op.XOR, Op.SUB}:
                p = int.from_bytes(vm.stack.peek(), 'big')
                # 这个地方是要比较是否选择当前函数，要选择当前函数执行，必然会使用判断条件判断是否要执行当前函数
                # EQ是将栈中原本的两个操作数进行比较操作
                if p == (1 if ret[0] == Op.EQ else 0):
                    inside_function = bytes(ret[2]).endswith(bytes_selector)
            continue

        match ret:a
            # case (Op.CALLDATALOAD,_,_,_):
            #     print("1")

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
                # offset表示CALLDATALOAD从calldata中取出数据的偏移量
                off = int.from_bytes(offset, 'big')
                if off >= 4 and off < 2**32:
                    vm.stack.pop()
                    # 有点明白意思了,只要是通过CALLDATALOAD从栈中加载出来的数据都是Arg类型
                    vm.stack.push(Arg(offset=off))
                    # print("1-----------------------")
                    # print(Arg(offset=off).__repr__())
                    # print("1-----------------------")
                    # 加载操作无法推断类型
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



