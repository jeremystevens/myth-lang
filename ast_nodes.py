class NumberNode:

    def __init__(
        self,
        value,
        line=None
    ):

        self.value = value
        self.line = line

    def __repr__(self):

        return (
            f"NumberNode({self.value})"
        )


class StringNode:

    def __init__(
        self,
        value,
        line=None
    ):

        self.value = value
        self.line = line

    def __repr__(self):

        return (
            f'StringNode("{self.value}")'
        )


class VariableNode:

    def __init__(
        self,
        name,
        line=None
    ):

        self.name = name
        self.line = line

    def __repr__(self):

        return (
            f"VariableNode({self.name})"
        )


class ListNode:

    def __init__(
        self,
        elements,
        line=None
    ):

        self.elements = elements
        self.line = line

    def __repr__(self):

        return (
            f"ListNode({self.elements})"
        )


class DictionaryNode:

    def __init__(
        self,
        pairs,
        line=None
    ):

        self.pairs = pairs
        self.line = line

    def __repr__(self):

        return (
            f"DictionaryNode({self.pairs})"
        )


class IndexNode:

    def __init__(
        self,
        collection,
        index,
        line=None
    ):

        self.collection = collection
        self.index = index
        self.line = line

    def __repr__(self):

        return (
            f"IndexNode("
            f"{self.collection}, "
            f"{self.index})"
        )


class IndexAssignNode:

    def __init__(
        self,
        collection,
        index,
        value,
        line=None
    ):

        self.collection = collection
        self.index = index
        self.value = value
        self.line = line

    def __repr__(self):

        return (
            f"IndexAssignNode("
            f"{self.collection}, "
            f"{self.index}, "
            f"{self.value})"
        )


class UnaryOperationNode:

    def __init__(
        self,
        operator,
        operand,
        line=None
    ):

        self.operator = operator
        self.operand = operand
        self.line = line

    def __repr__(self):

        return (
            f"UnaryOperationNode("
            f"'{self.operator}', "
            f"{self.operand})"
        )


class LogicalOperationNode:

    def __init__(
        self,
        left,
        operator,
        right,
        line=None
    ):

        self.left = left
        self.operator = operator
        self.right = right
        self.line = line

    def __repr__(self):

        return (
            f"LogicalOperationNode("
            f"{self.left}, "
            f"'{self.operator}', "
            f"{self.right})"
        )


class BinaryOperationNode:

    def __init__(
        self,
        left,
        operator,
        right,
        line=None
    ):

        self.left = left
        self.operator = operator
        self.right = right
        self.line = line

    def __repr__(self):

        return (
            f"BinaryOperationNode("
            f"{self.left}, "
            f"'{self.operator}', "
            f"{self.right})"
        )


class CompareNode:

    def __init__(
        self,
        left,
        operator,
        right,
        line=None
    ):

        self.left = left
        self.operator = operator
        self.right = right
        self.line = line

    def __repr__(self):

        return (
            f"CompareNode("
            f"{self.left}, "
            f"'{self.operator}', "
            f"{self.right})"
        )


class PrintNode:

    def __init__(
        self,
        value,
        line=None
    ):

        self.value = value
        self.line = line

    def __repr__(self):

        return (
            f"PrintNode({self.value})"
        )


class AssignNode:

    def __init__(
        self,
        name,
        value,
        line=None
    ):

        self.name = name
        self.value = value
        self.line = line

    def __repr__(self):

        return (
            f"AssignNode("
            f"{self.name}, "
            f"{self.value})"
        )


class ForNode:

    def __init__(
        self,
        variable,
        start,
        end,
        body,
        line=None
    ):

        self.variable = variable
        self.start = start
        self.end = end
        self.body = body
        self.line = line

    def __repr__(self):

        return (
            f"ForNode("
            f"variable={self.variable}, "
            f"start={self.start}, "
            f"end={self.end}, "
            f"body={self.body})"
        )


class ForEachNode:

    def __init__(
        self,
        variable,
        iterable,
        body,
        line=None
    ):

        self.variable = variable
        self.iterable = iterable
        self.body = body
        self.line = line

    def __repr__(self):

        return (
            f"ForEachNode("
            f"variable={self.variable}, "
            f"iterable={self.iterable}, "
            f"body={self.body})"
        )


class IfNode:

    def __init__(
        self,
        condition,
        true_body,
        false_body=None,
        line=None
    ):

        self.condition = condition
        self.true_body = true_body
        self.false_body = false_body
        self.line = line

    def __repr__(self):

        return (
            f"IfNode("
            f"condition={self.condition}, "
            f"true_body={self.true_body}, "
            f"false_body={self.false_body})"
        )


class WhileNode:

    def __init__(
        self,
        condition,
        body,
        line=None
    ):

        self.condition = condition
        self.body = body
        self.line = line

    def __repr__(self):

        return (
            f"WhileNode("
            f"condition={self.condition}, "
            f"body={self.body})"
        )


class FunctionNode:

    def __init__(
        self,
        name,
        params,
        body,
        line=None
    ):

        self.name = name
        self.params = params
        self.body = body
        self.line = line

    def __repr__(self):

        return (
            f"FunctionNode("
            f"name={self.name}, "
            f"params={self.params}, "
            f"body={self.body})"
        )


class CallNode:

    def __init__(
        self,
        name,
        args,
        line=None
    ):

        self.name = name
        self.args = args
        self.line = line

    def __repr__(self):

        return (
            f"CallNode("
            f"name={self.name}, "
            f"args={self.args})"
        )


class ReturnNode:

    def __init__(
        self,
        value,
        line=None
    ):

        self.value = value
        self.line = line

    def __repr__(self):

        return (
            f"ReturnNode({self.value})"
        )


class ImportNode:

    def __init__(
        self,
        path,
        line=None
    ):

        # The raw module path string as written
        # by the programmer, e.g. "utils" or
        # "math/helpers".  The interpreter is
        # responsible for resolving it to a file.
        self.path = path
        self.line = line

    def __repr__(self):

        return (
            f'ImportNode("{self.path}")'
        )