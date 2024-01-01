# evmole-源码解读
暂时只分析了和参数类型推断的相关代码

# 关键代码解读
整个evmole最关键的代码是vm.py文件和arguments.py的文件，vm.py实现区分函数参数过程中的EVM，arguments.py实现模拟EVM在执行不同类型参数时EVM的执行逻辑(区分参数类型)，注意evmole并不能区分参数个数以及多维元素，但是可以判断参数顺序。

整个区分参数类型的逻辑是从arguments.py中的函数：function_arguments开始。在具体的函数执行之前，需要先明白calldata的布局，下面以常见的参数类型的情况来说明。


静态类型数据在calldata中的存储：(仅仅只存放静态数据本身)

















