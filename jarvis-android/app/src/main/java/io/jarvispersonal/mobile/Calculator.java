package io.jarvispersonal.mobile;

/** Small bounded arithmetic parser; never evaluates code. */
public final class Calculator {
    private final String text;
    private int index = 0, depth = 0;
    private Calculator(String text) { this.text = text.replace('×','*').replace('÷','/').replace(',','.'); }
    public static double evaluate(String expression) {
        if (expression.length() > 160) throw new IllegalArgumentException("La operación es demasiado larga.");
        Calculator p = new Calculator(expression);
        double value = p.sum(); p.space();
        if (p.index != p.text.length() || !Double.isFinite(value)) throw new IllegalArgumentException("Revisa la operación.");
        return value;
    }
    private void space() { while(index < text.length() && Character.isWhitespace(text.charAt(index))) index++; }
    private boolean take(char c) { space(); if(index < text.length() && text.charAt(index)==c) { index++; return true; } return false; }
    private double sum() { double x=product(); while(true) { if(take('+'))x+=product(); else if(take('-'))x-=product(); else return x; } }
    private double product() { double x=atom(); while(true) { if(take('*'))x*=atom(); else if(take('/')) { double y=atom(); if(y==0)throw new IllegalArgumentException("No se puede dividir entre cero."); x/=y; } else return x; } }
    private double atom() {
        if (++depth > 24) throw new IllegalArgumentException("Demasiados paréntesis.");
        try {
            if(take('+'))return atom(); if(take('-'))return -atom();
            if(take('(')) { double x=sum(); if(!take(')'))throw new IllegalArgumentException("Falta cerrar un paréntesis."); return x; }
            space(); int start=index;
            while(index<text.length() && (Character.isDigit(text.charAt(index)) || text.charAt(index)=='.')) index++;
            if(start==index)throw new IllegalArgumentException("Usa números, paréntesis y + − × ÷.");
            try { return Double.parseDouble(text.substring(start,index)); }
            catch(NumberFormatException e) { throw new IllegalArgumentException("Número inválido."); }
        } finally { depth--; }
    }
}
