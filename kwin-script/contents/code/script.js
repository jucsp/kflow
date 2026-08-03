.pragma library

/*
    KFlow — Motor de cálculo puro (sin dependencias de KWin/QML).
    Estas funciones son deterministas y solo trabajan con números/objetos planos
    para poder ser invocadas desde main.qml y, eventualmente, cubiertas por tests.
*/

var DEFAULT_DESKTOP_THRESHOLD = 4;

/**
 * Aplica los márgenes externos (outer margins) sobre el área de pantalla utilizable
 * y devuelve el rectángulo resultante donde se distribuirán las ventanas.
 */
function applyOuterMargins(area, margins) {
    var top = margins.top || 0;
    var bottom = margins.bottom || 0;
    var left = margins.left || 0;
    var right = margins.right || 0;

    var width = area.width - left - right;
    var height = area.height - top - bottom;

    return {
        x: area.x + left,
        y: area.y + top,
        width: width > 0 ? width : 0,
        height: height > 0 ? height : 0
    };
}

/**
 * Particionado binario recursivo (BSP) que distribuye `count` ventanas dentro
 * del rectángulo (x, y, w, h), separándolas con `gap` píxeles. En cada nivel
 * se divide por el lado más largo, y el reparto de ancho/alto es proporcional
 * a cuántas ventanas caen en cada mitad, para que el árbol quede balanceado
 * cuando `count` no es potencia de 2.
 */
function bspSplit(x, y, w, h, count, gap) {
    if (count <= 0) {
        return [];
    }
    if (count === 1) {
        return [{ x: x, y: y, width: w, height: h }];
    }

    var firstCount = Math.ceil(count / 2);
    var secondCount = count - firstCount;
    var splitRatio = firstCount / count;

    if (w >= h) {
        var firstWidth = Math.max(0, Math.floor((w - gap) * splitRatio));
        var secondWidth = Math.max(0, w - gap - firstWidth);
        var left = bspSplit(x, y, firstWidth, h, firstCount, gap);
        var right = bspSplit(x + firstWidth + gap, y, secondWidth, h, secondCount, gap);
        return left.concat(right);
    }

    var firstHeight = Math.max(0, Math.floor((h - gap) * splitRatio));
    var secondHeight = Math.max(0, h - gap - firstHeight);
    var top = bspSplit(x, y, w, firstHeight, firstCount, gap);
    var bottom = bspSplit(x, y + firstHeight + gap, w, secondHeight, secondCount, gap);
    return top.concat(bottom);
}

/**
 * Calcula el layout final de tiling dinámico para `windowCount` ventanas dentro
 * de `screenArea`, aplicando primero los márgenes externos y luego el gap interno.
 */
function computeLayout(screenArea, innerGap, outerMargins, windowCount) {
    var usable = applyOuterMargins(screenArea, outerMargins);
    if (windowCount <= 0) {
        return [];
    }
    return bspSplit(usable.x, usable.y, usable.width, usable.height, windowCount, innerGap || 0);
}

/**
 * Decide si corresponde crear un nuevo escritorio virtual porque el escritorio
 * activo alcanzó (o superó) el umbral de ventanas configurado.
 */
function shouldCreateDesktop(windowCount, threshold) {
    var limit = threshold || DEFAULT_DESKTOP_THRESHOLD;
    return windowCount >= limit;
}

/**
 * Decide si un escritorio vacío debe eliminarse. Nunca se elimina si es el
 * único escritorio restante (KWin siempre requiere al menos uno).
 */
function shouldRemoveDesktop(windowCount, totalDesktops) {
    return windowCount === 0 && totalDesktops > 1;
}
