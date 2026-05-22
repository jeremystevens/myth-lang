class NumberNode:

    def __init__(
        self,
        value,
        line=None,
        source_file=None
    ):

        self.value = value
        self.line = line
        self.source_file = source_file

    def __repr__(self):

        return (
            f"NumberNode({self.value})"
        )


class StringNode:

    def __init__(
        self,
        value,
        line=None,
        source_file=None
    ):

        self.value = value
        self.line = line
        self.source_file = source_file

    def __repr__(self):

        return (
            f'StringNode("{self.value}")'
        )


class VariableNode:

    def __init__(
        self,
        name,
        line=None,
        source_file=None
    ):

        self.name = name
        self.line = line
        self.source_file = source_file

    def __repr__(self):

        return (
            f"VariableNode({self.name})"
        )


class ListNode:

    def __init__(
        self,
        elements,
        line=None,
        source_file=None
    ):

        self.elements = elements
        self.line = line
        self.source_file = source_file

    def __repr__(self):

        return (
            f"ListNode({self.elements})"
        )


class DictionaryNode:

    def __init__(
        self,
        pairs,
        line=None,
        source_file=None
    ):

        self.pairs = pairs
        self.line = line
        self.source_file = source_file

    def __repr__(self):

        return (
            f"DictionaryNode({self.pairs})"
        )


class IndexNode:

    def __init__(
        self,
        collection,
        index,
        line=None,
        source_file=None
    ):

        self.collection = collection
        self.index = index
        self.line = line
        self.source_file = source_file

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
        line=None,
        source_file=None
    ):

        self.collection = collection
        self.index = index
        self.value = value
        self.line = line
        self.source_file = source_file

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
        line=None,
        source_file=None
    ):

        self.operator = operator
        self.operand = operand
        self.line = line
        self.source_file = source_file

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
        line=None,
        source_file=None
    ):

        self.left = left
        self.operator = operator
        self.right = right
        self.line = line
        self.source_file = source_file

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
        line=None,
        source_file=None
    ):

        self.left = left
        self.operator = operator
        self.right = right
        self.line = line
        self.source_file = source_file

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
        line=None,
        source_file=None
    ):

        self.left = left
        self.operator = operator
        self.right = right
        self.line = line
        self.source_file = source_file

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
        line=None,
        source_file=None
    ):

        self.value = value
        self.line = line
        self.source_file = source_file

    def __repr__(self):

        return (
            f"PrintNode({self.value})"
        )


class AssignNode:

    def __init__(
        self,
        name,
        value,
        line=None,
        source_file=None
    ):

        self.name = name
        self.value = value
        self.line = line
        self.source_file = source_file

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
        line=None,
        source_file=None
    ):

        self.variable = variable
        self.start = start
        self.end = end
        self.body = body
        self.line = line
        self.source_file = source_file

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
        line=None,
        source_file=None
    ):

        self.variable = variable
        self.iterable = iterable
        self.body = body
        self.line = line
        self.source_file = source_file

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
        line=None,
        source_file=None
    ):

        self.condition = condition
        self.true_body = true_body
        self.false_body = false_body
        self.line = line
        self.source_file = source_file

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
        line=None,
        source_file=None
    ):

        self.condition = condition
        self.body = body
        self.line = line
        self.source_file = source_file

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
        line=None,
        source_file=None
    ):

        self.name = name
        self.params = params
        self.body = body
        self.line = line
        self.source_file = source_file

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
        line=None,
        source_file=None
    ):

        self.name = name
        self.args = args
        self.line = line
        self.source_file = source_file

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
        line=None,
        source_file=None
    ):

        self.value = value
        self.line = line
        self.source_file = source_file

    def __repr__(self):

        return (
            f"ReturnNode({self.value})"
        )


class ImportNode:

    def __init__(
        self,
        path,
        line=None,
        source_file=None
    ):

        # The raw module path string as written
        # by the programmer, e.g. "utils" or
        # "math/helpers".  The interpreter is
        # responsible for resolving it to a file.
        self.path = path
        self.line = line
        self.source_file = source_file

    def __repr__(self):

        return (
            f'ImportNode("{self.path}")'
        )


# ===========================================================================
# PHASE 6 — NAMESPACES & MODULES
# ===========================================================================


class FromImportNode:
    """
    Selective import — brings specific names into the caller's scope.

      from utils import double
      from utils import double, triple, square

    Attributes
    ----------
    path  : str        — module path (same as ImportNode)
    names : list[str]  — names to import into the local scope
    line  : int
    """

    def __init__(self, path, names, line=None, source_file=None):
        self.path        = path
        self.names       = names
        self.line        = line
        self.source_file = source_file

    def __repr__(self):
        return (
            f'FromImportNode("{self.path}", '
            f'{self.names})'
        )


class ExportNode:
    """
    Marks a name as part of this module's public API.

      export double
      export Player

    Only exported names are visible when a caller does:

      import utils          # → utils.double() works
                            # → utils._private() fails

    Modules with no export statements export everything
    (backwards-compatible behaviour).

    Attributes
    ----------
    name : str  — the identifier being exported
    line : int
    """

    def __init__(self, name, line=None, source_file=None):
        self.name = name
        self.line = line
        self.source_file = source_file

    def __repr__(self):
        return f'ExportNode("{self.name}")'


class ClassNode:
    """
    Represents a class definition.

      class ClassName
          init param1 param2
              this.x = param1
          end
          method do_something arg
              ...
          end
      end

    Attributes
    ----------
    name        : str   — the class name
    params      : list  — constructor parameter names (from `init`)
    init_body   : list  — AST nodes for the constructor body
    methods     : dict  — name → FunctionNode for each method
    line        : int
    """

    def __init__(
        self,
        name,
        params,
        init_body,
        methods,
        line=None,
    ):

        self.name      = name
        self.params    = params
        self.init_body = init_body
        self.methods   = methods
        self.line      = line

    def __repr__(self):

        return (
            f"ClassNode("
            f"name={self.name}, "
            f"params={self.params}, "
            f"methods={list(self.methods.keys())})"
        )


class MethodCallNode:
    """
    Represents calling a method on an object.

      obj.method_name(arg1, arg2)

    Attributes
    ----------
    obj_expr    : AST node  — the object expression
    method_name : str
    args        : list      — argument AST nodes
    line        : int
    """

    def __init__(
        self,
        obj_expr,
        method_name,
        args,
        line=None,
    ):

        self.obj_expr    = obj_expr
        self.method_name = method_name
        self.args        = args
        self.line        = line

    def __repr__(self):

        return (
            f"MethodCallNode("
            f"{self.obj_expr}.{self.method_name}"
            f"({self.args}))"
        )


class PropertyAccessNode:
    """
    Represents reading a property from an object.

      obj.property_name

    Attributes
    ----------
    obj_expr      : AST node  — the object expression
    property_name : str
    line          : int
    """

    def __init__(
        self,
        obj_expr,
        property_name,
        line=None,
    ):

        self.obj_expr      = obj_expr
        self.property_name = property_name
        self.line          = line

    def __repr__(self):

        return (
            f"PropertyAccessNode("
            f"{self.obj_expr}.{self.property_name})"
        )


class PropertyAssignNode:
    """
    Represents assigning a value to an object property.

      obj.property_name = value
      this.hp = 100

    Attributes
    ----------
    obj_expr      : AST node  — the object expression
    property_name : str
    value         : AST node
    line          : int
    """

    def __init__(
        self,
        obj_expr,
        property_name,
        value,
        line=None,
    ):

        self.obj_expr      = obj_expr
        self.property_name = property_name
        self.value         = value
        self.line          = line

    def __repr__(self):

        return (
            f"PropertyAssignNode("
            f"{self.obj_expr}.{self.property_name}"
            f" = {self.value})"
        )