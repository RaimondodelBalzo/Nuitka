#     Copyright 2013, Kay Hayen, mailto:kay.hayen@gmail.com
#
#     Part of "Nuitka", an optimizing Python compiler that is compatible and
#     integrates with CPython, but also works on its own.
#
#     Licensed under the Apache License, Version 2.0 (the "License");
#     you may not use this file except in compliance with the License.
#     You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#     Unless required by applicable law or agreed to in writing, software
#     distributed under the License is distributed on an "AS IS" BASIS,
#     WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#     See the License for the specific language governing permissions and
#     limitations under the License.
#
""" Reformulation of classes

Consult the developmer manual for information. TODO: Add ability to sync source code
comments with developer manual sections.

"""

from nuitka.nodes.VariableRefNodes import (
    ExpressionTargetVariableRef,
    ExpressionVariableRef,
    ExpressionTempVariableRef,
    StatementTempBlock
)
from nuitka.nodes.ConstantRefNodes import ExpressionConstantRef
from nuitka.nodes.BuiltinRefNodes import ExpressionBuiltinRef
from nuitka.nodes.ComparisonNodes import ExpressionComparison

from nuitka.nodes.CallNodes import (
    ExpressionCallNoKeywords,
    ExpressionCall
)
from nuitka.nodes.TypeNodes import ExpressionBuiltinType1
from nuitka.nodes.AttributeNodes import (
    ExpressionAttributeLookup,
    ExpressionBuiltinHasattr
)
from nuitka.nodes.SubscriptNodes import ExpressionSubscriptLookup
from nuitka.nodes.FunctionNodes import (
    ExpressionFunctionCreation,
    ExpressionFunctionBody,
    ExpressionFunctionCall,
    ExpressionFunctionRef
)
from nuitka.nodes.ClassNodes import ExpressionSelectMetaclass
from nuitka.nodes.ContainerMakingNodes import (
    ExpressionKeyValuePair,
    ExpressionMakeTuple,
    ExpressionMakeDict
)
from nuitka.nodes.ContainerOperationNodes import (
    StatementDictOperationRemove,
    ExpressionDictOperationGet
)
from nuitka.nodes.StatementNodes import StatementsSequence

from nuitka.nodes.ConditionalNodes import (
    ExpressionConditional,
    StatementConditional
)
from nuitka.nodes.ReturnNodes import StatementReturn
from nuitka.nodes.AssignNodes import StatementAssignmentVariable

from nuitka.nodes.GlobalsLocalsNodes import (
    StatementSetLocals,
    ExpressionBuiltinLocals
)

from nuitka.nodes.ParameterSpec import ParameterSpec

from .Helpers import (
    makeStatementsSequence,
    buildStatementsNode,
    extractDocFromBody,
    buildNodeList,
    buildNode,
    getKind
)

from nuitka import Utils

# TODO: Once we start to modify these, we should make sure, the copy is not shared.
make_class_parameters = ParameterSpec(
    name          = "class",
    normal_args   = (),
    list_star_arg = None,
    dict_star_arg = None,
    default_count = 0,
    kw_only_args  = ()
)


def _buildClassNode3( provider, node, source_ref ):
    # Many variables, due to the huge re-formulation that is going on here, which just has
    # the complexity, pylint: disable=R0914

    # This function is the Python3 special case with special re-formulation as according
    # to developer manual.
    class_statements, class_doc = extractDocFromBody( node )

    # The result will be a temp block that holds the temporary variables.
    result = StatementTempBlock(
        source_ref = source_ref
    )

    tmp_bases = result.getTempVariable( "bases" )
    tmp_class_decl_dict = result.getTempVariable( "class_decl_dict" )
    tmp_metaclass = result.getTempVariable( "metaclass" )
    tmp_prepared = result.getTempVariable( "prepared" )

    class_creation_function = ExpressionFunctionBody(
        provider   = provider,
        is_class   = True,
        parameters = make_class_parameters,
        name       = node.name,
        doc        = class_doc,
        source_ref = source_ref
    )

    # Hack:
    class_creation_function.parent = provider

    body = buildStatementsNode(
        provider   = class_creation_function,
        nodes      = class_statements,
        frame      = True,
        source_ref = source_ref
    )

    if body is not None:
        # The frame guard has nothing to tell its line number to.
        body.source_ref = source_ref.atInternal()

    statements = [
        StatementSetLocals(
            new_locals = ExpressionTempVariableRef(
                variable   = tmp_prepared.makeReference( result ),
                source_ref = source_ref
            ),
            source_ref = source_ref.atInternal()
        ),
        StatementAssignmentVariable(
            variable_ref = ExpressionTargetVariableRef(
                variable_name = "__module__",
                source_ref    = source_ref
            ),
            source        = ExpressionConstantRef(
                constant   = provider.getParentModule().getName(),
                source_ref = source_ref
            ),
            source_ref   = source_ref.atInternal()
        )
    ]

    if class_doc is not None:
        statements.append(
            StatementAssignmentVariable(
                variable_ref = ExpressionTargetVariableRef(
                    variable_name = "__doc__",
                    source_ref    = source_ref
                ),
                source        = ExpressionConstantRef(
                    constant   = class_doc,
                    source_ref = source_ref
                ),
                source_ref   = source_ref.atInternal()
            )
        )

    statements += [
        body,
        StatementAssignmentVariable(
            variable_ref = ExpressionTargetVariableRef(
                variable_name = "__class__",
                source_ref    = source_ref
            ),
            source       = ExpressionCall(
                called     = ExpressionTempVariableRef(
                    variable   = tmp_metaclass.makeReference( result ),
                    source_ref = source_ref
                ),
                args       = ExpressionMakeTuple(
                    elements   = (
                        ExpressionConstantRef(
                            constant   = node.name,
                            source_ref = source_ref
                        ),
                        ExpressionTempVariableRef(
                            variable   = tmp_bases.makeReference( result ),
                            source_ref = source_ref
                        ),
                        ExpressionBuiltinLocals(
                            source_ref = source_ref
                        )
                    ),
                    source_ref = source_ref
                ),
                kw         = ExpressionTempVariableRef(
                    variable   = tmp_class_decl_dict.makeReference( result ),
                    source_ref = source_ref
                ),
                source_ref = source_ref
            ),
            source_ref   = source_ref.atInternal()
        ),
        StatementReturn(
            expression = ExpressionVariableRef(
                variable_name = "__class__",
                source_ref    = source_ref
            ),
            source_ref = source_ref.atInternal()
        )
    ]

    body = makeStatementsSequence(
        statements = statements,
        allow_none = True,
        source_ref = source_ref
    )

    # The class body is basically a function that implicitely, at the end returns its
    # locals and cannot have other return statements contained.

    class_creation_function.setBody( body )

    # The class body is basically a function that implicitely, at the end returns its
    # created class and cannot have other return statements contained.

    decorated_body = ExpressionFunctionCall(
        function   = ExpressionFunctionCreation(
            function_ref = ExpressionFunctionRef(
                function_body = class_creation_function,
                source_ref    = source_ref
            ),
            defaults     = (),
            kw_defaults  = None,
            annotations  = None,
            source_ref   = source_ref
        ),
        values     = (),
        source_ref = source_ref
    )

    for decorator in buildNodeList( provider, reversed( node.decorator_list ), source_ref ):
        decorated_body = ExpressionCallNoKeywords(
            called     = decorator,
            args       = ExpressionMakeTuple(
                elements   = ( decorated_body, ),
                source_ref = source_ref
            ),
            source_ref = decorator.getSourceReference()
        )

    statements = [
        StatementAssignmentVariable(
            variable_ref = ExpressionTempVariableRef(
                variable   = tmp_bases.makeReference( result ),
                source_ref = source_ref
            ),
            source       = ExpressionMakeTuple(
                elements   = buildNodeList( provider, node.bases, source_ref ),
                source_ref = source_ref
            ),
            source_ref   = source_ref
        ),
        StatementAssignmentVariable(
            variable_ref = ExpressionTempVariableRef(
                variable   = tmp_class_decl_dict.makeReference( result ),
                source_ref = source_ref
            ),
            source       = ExpressionMakeDict(
                pairs      = [
                    ExpressionKeyValuePair(
                        key        = ExpressionConstantRef(
                            constant   = keyword.arg,
                            source_ref = source_ref
                        ),
                        value      = buildNode( provider, keyword.value, source_ref ),
                        source_ref = source_ref
                    )
                    for keyword in
                    node.keywords
                ],
                source_ref = source_ref
            ),
            source_ref = source_ref
        ),
        StatementAssignmentVariable(
            variable_ref = ExpressionTempVariableRef(
                variable   = tmp_metaclass.makeReference( result ),
                source_ref = source_ref
            ),
            source       = ExpressionSelectMetaclass(
                metaclass = ExpressionConditional(
                    condition = ExpressionComparison(
                        comparator = "In",
                        left       = ExpressionConstantRef(
                            constant   = "metaclass",
                            source_ref = source_ref
                        ),
                        right      = ExpressionTempVariableRef(
                            variable   = tmp_class_decl_dict.makeReference( result ),
                            source_ref = source_ref
                        ),
                        source_ref = source_ref
                    ),
                    yes_expression = ExpressionDictOperationGet(
                        dicte      = ExpressionTempVariableRef(
                            variable   = tmp_class_decl_dict.makeReference( result ),
                            source_ref = source_ref
                        ),
                        key        = ExpressionConstantRef(
                            constant   = "metaclass",
                            source_ref = source_ref
                        ),
                        source_ref = source_ref
                    ),
                    no_expression  = ExpressionConditional(
                        condition      = ExpressionTempVariableRef(
                            variable   = tmp_bases.makeReference( result ),
                            source_ref = source_ref
                        ),
                        no_expression  = ExpressionBuiltinRef(
                            builtin_name = "type",
                            source_ref   = source_ref
                        ),
                        yes_expression = ExpressionBuiltinType1(
                            value      = ExpressionSubscriptLookup(
                                expression = ExpressionTempVariableRef(
                                    variable   = tmp_bases.makeReference( result ),
                                    source_ref = source_ref
                                ),
                                subscript  = ExpressionConstantRef(
                                    constant   = 0,
                                    source_ref = source_ref
                                ),
                                source_ref = source_ref
                            ),
                            source_ref = source_ref
                        ),
                        source_ref     = source_ref
                    ),
                    source_ref     = source_ref
                ),
                bases     = ExpressionTempVariableRef(
                    variable   = tmp_bases.makeReference( result ),
                    source_ref = source_ref
                ),
                source_ref = source_ref
            ),
            source_ref = source_ref
        ),
        StatementConditional(
            condition  = ExpressionComparison(
                comparator = "In",
                left       = ExpressionConstantRef(
                    constant   = "metaclass",
                    source_ref = source_ref
                ),
                right      = ExpressionTempVariableRef(
                    variable   = tmp_class_decl_dict.makeReference( result ),
                    source_ref = source_ref
                ),
                source_ref = source_ref
            ),
            no_branch  = None,
            yes_branch = StatementsSequence(
                statements = (
                    StatementDictOperationRemove(
                        dicte = ExpressionTempVariableRef(
                            variable   = tmp_class_decl_dict.makeReference( result ),
                            source_ref = source_ref
                        ),
                        key   = ExpressionConstantRef(
                            constant   = "metaclass",
                            source_ref = source_ref
                        ),
                        source_ref = source_ref
                    ),
                ),
                source_ref = source_ref
            ),
            source_ref = source_ref
        ),
        StatementAssignmentVariable(
            variable_ref = ExpressionTempVariableRef(
                variable   = tmp_prepared.makeReference( result ),
                source_ref = source_ref
            ),
            source       = ExpressionConditional(
                condition = ExpressionBuiltinHasattr(
                    object     = ExpressionTempVariableRef(
                        variable   = tmp_metaclass.makeReference( result ),
                        source_ref = source_ref
                    ),
                    name       = ExpressionConstantRef(
                        constant   = "__prepare__",
                        source_ref = source_ref
                    ),
                    source_ref = source_ref
                ),
                no_expression = ExpressionConstantRef(
                    constant   = {},
                    source_ref = source_ref
                ),
                yes_expression = ExpressionCall(
                    called     = ExpressionAttributeLookup(
                        expression     = ExpressionTempVariableRef(
                            variable   = tmp_metaclass.makeReference( result ),
                            source_ref = source_ref
                        ),
                        attribute_name = "__prepare__",
                        source_ref     = source_ref
                    ),
                    args       = ExpressionMakeTuple(
                        elements   = (
                            ExpressionConstantRef(
                                constant = node.name,
                                source_ref     = source_ref
                            ),
                            ExpressionTempVariableRef(
                                variable   = tmp_bases.makeReference( result ),
                                source_ref = source_ref
                            )
                        ),
                        source_ref = source_ref
                    ),
                    kw         = ExpressionTempVariableRef(
                        variable   = tmp_class_decl_dict.makeReference( result ),
                        source_ref = source_ref
                    ),
                    source_ref = source_ref
                ),
                source_ref = source_ref
            ),
            source_ref = source_ref
        ),
        StatementAssignmentVariable(
            variable_ref = ExpressionTargetVariableRef(
                variable_name = node.name,
                source_ref    = source_ref
            ),
            source     = decorated_body,
            source_ref = source_ref
        )
    ]

    result.setBody(
        StatementsSequence(
            statements = statements,
            source_ref = source_ref
        )
    )

    return result


def _buildClassNode2( provider, node, source_ref ):
    class_statements, class_doc = extractDocFromBody( node )

    # This function is the Python3 special case with special re-formulation as according
    # to developer manual.

    # The result will be a temp block that holds the temporary variables.
    result = StatementTempBlock(
        source_ref = source_ref
    )

    tmp_bases = result.getTempVariable( "bases" )
    tmp_class_dict = result.getTempVariable( "class_dict" )
    tmp_metaclass = result.getTempVariable( "metaclass" )
    tmp_class = result.getTempVariable( "class" )

    class_creation_function = ExpressionFunctionBody(
        provider   = provider,
        is_class   = True,
        parameters = make_class_parameters,
        name       = node.name,
        doc        = class_doc,
        source_ref = source_ref
    )

    body = buildStatementsNode(
        provider   = class_creation_function,
        nodes      = class_statements,
        frame      = True,
        source_ref = source_ref
    )

    if body is not None:
        # The frame guard has nothing to tell its line number to.
        body.source_ref = source_ref.atInternal()

    # The class body is basically a function that implicitely, at the end returns its
    # locals and cannot have other return statements contained, and starts out with a
    # variables "__module__" and potentially "__doc__" set.
    statements = [
        StatementAssignmentVariable(
            variable_ref = ExpressionTargetVariableRef(
                variable_name = "__module__",
                source_ref    = source_ref
            ),
            source        = ExpressionConstantRef(
                constant   = provider.getParentModule().getName(),
                source_ref = source_ref
            ),
            source_ref   = source_ref.atInternal()
        )
    ]

    if class_doc is not None:
        statements.append(
            StatementAssignmentVariable(
                variable_ref = ExpressionTargetVariableRef(
                    variable_name = "__doc__",
                    source_ref    = source_ref
                ),
                source        = ExpressionConstantRef(
                    constant   = class_doc,
                    source_ref = source_ref
                ),
                source_ref   = source_ref.atInternal()
            )
        )

    statements += [
        body,
        StatementReturn(
            expression = ExpressionBuiltinLocals(
                source_ref = source_ref
            ),
            source_ref = source_ref.atInternal()
        )
    ]

    body = makeStatementsSequence(
        statements = statements,
        allow_none = True,
        source_ref = source_ref
    )

    # The class body is basically a function that implicitely, at the end returns its
    # locals and cannot have other return statements contained.

    class_creation_function.setBody( body )

    statements = [
        StatementAssignmentVariable(
            variable_ref = ExpressionTempVariableRef(
                variable   = tmp_bases.makeReference( result ),
                source_ref = source_ref
            ),
            source       = ExpressionMakeTuple(
                elements   = buildNodeList( provider, node.bases, source_ref ),
                source_ref = source_ref
            ),
            source_ref   = source_ref
        ),
        StatementAssignmentVariable(
            variable_ref = ExpressionTempVariableRef(
                variable   = tmp_class_dict.makeReference( result ),
                source_ref = source_ref
            ),
            source       =   ExpressionFunctionCall(
                function = ExpressionFunctionCreation(
                    function_ref = ExpressionFunctionRef(
                        function_body = class_creation_function,
                        source_ref    = source_ref
                    ),
                    defaults     = (),
                    kw_defaults  = None,
                    annotations  = None,
                    source_ref   = source_ref
                ),
                values     = (),
                source_ref = source_ref
            ),
            source_ref   = source_ref
        ),
        StatementAssignmentVariable(
            variable_ref = ExpressionTempVariableRef(
                variable   = tmp_metaclass.makeReference( result ),
                source_ref = source_ref
            ),
            source       = ExpressionConditional(
                condition =  ExpressionComparison(
                    comparator = "In",
                    left       = ExpressionConstantRef(
                        constant   = "__metaclass__",
                        source_ref = source_ref
                    ),
                    right      = ExpressionTempVariableRef(
                        variable   = tmp_class_dict.makeReference( result ),
                        source_ref = source_ref
                    ),
                    source_ref = source_ref
                ),
                yes_expression = ExpressionDictOperationGet(
                    dicte = ExpressionTempVariableRef(
                        variable   = tmp_class_dict.makeReference( result ),
                        source_ref = source_ref
                    ),
                    key   = ExpressionConstantRef(
                        constant   = "__metaclass__",
                        source_ref = source_ref
                    ),
                    source_ref = source_ref
                ),
                no_expression = ExpressionSelectMetaclass(
                    metaclass = None,
                    bases     = ExpressionTempVariableRef(
                        variable   = tmp_bases.makeReference( result ),
                        source_ref = source_ref
                    ),
                    source_ref = source_ref
                ),
                source_ref = source_ref
            ),
            source_ref = source_ref
        ),
        StatementAssignmentVariable(
            variable_ref = ExpressionTempVariableRef(
                variable   = tmp_class.makeReference( result ),
                source_ref = source_ref
            ),
            source     = ExpressionCallNoKeywords(
                called         = ExpressionTempVariableRef(
                    variable   = tmp_metaclass.makeReference( result ),
                    source_ref = source_ref
                ),
                args           = ExpressionMakeTuple(
                    elements   = (
                        ExpressionConstantRef(
                            constant = node.name,
                            source_ref     = source_ref
                        ),
                        ExpressionTempVariableRef(
                            variable   = tmp_bases.makeReference( result ),
                            source_ref = source_ref
                        ),
                        ExpressionTempVariableRef(
                            variable   = tmp_class_dict.makeReference( result ),
                            source_ref = source_ref
                        )
                    ),
                    source_ref = source_ref
                ),
                source_ref = source_ref
            ),
            source_ref = source_ref
        )
    ]

    for decorator in buildNodeList( provider, reversed( node.decorator_list ), source_ref ):
        statements.append(
            StatementAssignmentVariable(
                variable_ref = ExpressionTempVariableRef(
                    variable   = tmp_class.makeReference( result ),
                    source_ref = source_ref
                ),
                source       = ExpressionCallNoKeywords(
                    called     = decorator,
                    args       = ExpressionMakeTuple(
                        elements  = (
                            ExpressionTempVariableRef(
                                variable   = tmp_class.makeReference( result ),
                                source_ref = source_ref
                            ),
                        ),
                        source_ref = source_ref
                    ),
                    source_ref = decorator.getSourceReference()
                ),
                source_ref   = decorator.getSourceReference()
            )
        )

    statements.append(
        StatementAssignmentVariable(
            variable_ref = ExpressionTargetVariableRef(
                variable_name = node.name,
                source_ref    = source_ref
            ),
            source     = ExpressionTempVariableRef(
                variable   = tmp_class.makeReference( result ),
                source_ref = source_ref
            ),
            source_ref = source_ref
        )
    )

    result.setBody(
        StatementsSequence(
            statements = statements,
            source_ref = source_ref
        )
    )

    return result

def buildClassNode( provider, node, source_ref ):
    assert getKind( node ) == "ClassDef"

    # Python3 and Python3 are similar, but fundamentally different, so handle them in
    # dedicated code.

    if Utils.python_version >= 300:
        return _buildClassNode3( provider, node, source_ref )
    else:
        return _buildClassNode2( provider, node, source_ref )
