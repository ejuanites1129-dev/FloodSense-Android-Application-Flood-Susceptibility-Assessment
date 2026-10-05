import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';

/// Reports the natural content height, independently of the scroll viewport.
/// This lets a draggable panel stop growing when all its content already fits.
class MeasuredScrollView extends StatelessWidget {
  const MeasuredScrollView({
    required this.controller,
    required this.onHeightChanged,
    required this.children,
    this.padding = EdgeInsets.zero,
    super.key,
  });

  final ScrollController? controller;
  final ValueChanged<double> onHeightChanged;
  final List<Widget> children;
  final EdgeInsetsGeometry padding;

  @override
  Widget build(BuildContext context) => SingleChildScrollView(
    controller: controller,
    child: _ContentHeightReporter(
      onHeightChanged: onHeightChanged,
      child: Padding(
        padding: padding,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: children,
        ),
      ),
    ),
  );
}

class _ContentHeightReporter extends SingleChildRenderObjectWidget {
  const _ContentHeightReporter({
    required this.onHeightChanged,
    required super.child,
  });
  final ValueChanged<double> onHeightChanged;

  @override
  RenderObject createRenderObject(BuildContext context) =>
      _ContentHeightRenderBox(onHeightChanged);

  @override
  void updateRenderObject(
    BuildContext context,
    _ContentHeightRenderBox renderObject,
  ) {
    renderObject.onHeightChanged = onHeightChanged;
  }
}

class _ContentHeightRenderBox extends RenderProxyBox {
  _ContentHeightRenderBox(this.onHeightChanged);
  ValueChanged<double> onHeightChanged;
  double? _reportedHeight;

  @override
  void performLayout() {
    super.performLayout();
    final height = size.height;
    if (_reportedHeight == height) return;
    _reportedHeight = height;
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (attached && size.height == height) onHeightChanged(height);
    });
  }
}
