from antlr4 import *
from JavaLexer import JavaLexer
from JavaParser import JavaParser
from JavaParserListener import JavaParserListener
from collections import defaultdict


class MethodExtractor(JavaParserListener):
    def __init__(self, tokens: CommonTokenStream):
        self.tokens = tokens
        self.methods = defaultdict(str)

    def enterClassDeclaration(self, ctx: JavaParser.ClassDeclarationContext):
        print(ctx.identifier().getText())

    def enterMethodDeclaration(self, ctx: JavaParser.MethodDeclarationContext):
        start_index = ctx.start.tokenIndex
        stop_index = ctx.stop.tokenIndex

        # トークンストリームからテキストを抽出
        identifier = ctx.identifier().getText()
        method_text = self.tokens.getText(start=start_index, stop=stop_index)

        self.methods[identifier] = method_text


def parse_java_code(java_code):
    input_stream = InputStream(java_code)
    lexer = JavaLexer(input_stream)
    stream = CommonTokenStream(lexer)
    parser = JavaParser(stream)
    tree = parser.compilationUnit()

    extractor = MethodExtractor(stream)
    walker = ParseTreeWalker()
    walker.walk(extractor, tree)
    return extractor


def extract_method(java_code, method_name):
    extractor = parse_java_code(java_code)
    return extractor.methods[method_name]


if __name__ == "__main__":
    with open(".orig/AbstractJavaCodegenTest.java.orig", mode="r") as f:
        java_code = f.read()

    extracted_method = extract_method(
        java_code, "getTypeDeclarationGivenImportMappingTest"
    )

    print(extracted_method)
