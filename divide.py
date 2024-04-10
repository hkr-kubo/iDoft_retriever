from antlr4 import *
from JavaLexer import JavaLexer
from JavaParser import JavaParser
from JavaParserListener import JavaParserListener


class MethodExtractor(JavaParserListener):
    def __init__(self, tokens: CommonTokenStream):
        self.tokens = tokens

    def enterClassDeclaration(self, ctx: JavaParser.ClassDeclarationContext):
        print(ctx.identifier().getText())

    def enterClassBodyDeclaration(self, ctx: JavaParser.ClassBodyDeclarationContext):
        start_index = ctx.start.tokenIndex
        stop_index = ctx.stop.tokenIndex

        # トークンストリームからテキストを抽出
        method_text = self.tokens.getText(start=start_index, stop=stop_index)

        identifier = ctx.memberDeclaration().methodDeclaration().identifier().getText()
        print(identifier)
        print(method_text)


def parse_java_code(java_code):
    input_stream = InputStream(java_code)
    lexer = JavaLexer(input_stream)
    stream = CommonTokenStream(lexer)
    parser = JavaParser(stream)
    tree = parser.compilationUnit()

    extractor = MethodExtractor(stream)
    walker = ParseTreeWalker()
    walker.walk(extractor, tree)


java_code = """
public class HelloWorld {
    public static void main(String[] args) {
        System.out.println("Hello, world!");
        System.out.println("Hello, world!");
    }
}
"""

parse_java_code(java_code)
